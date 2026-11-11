import datetime
import logging

from dotenv import load_dotenv
from pymongo import MongoClient

from .embeddings import runpod_api_pipeline
from .mongo import db as default_mongodb

load_dotenv()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def connect_custom_mongodb(mongodb_srv, customdb_name):
    uri = mongodb_srv
    custom_client = MongoClient(uri)

    # Send a ping to confirm a successful connection
    try:
        custom_client.admin.command('ping')
        logger.info("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        logger.info(e)
    custom_db = custom_client[customdb_name]
    custom_collection = custom_db['document-kb']

    return custom_collection


def check_unique_id(mongodb_srv, unique_id, customdb_name):
    custom_collection = connect_custom_mongodb(mongodb_srv, customdb_name)
    existing_document = custom_collection.find_one({"unique_id": unique_id})
    if existing_document:
        raise ValueError(f"Document with unique_id '{unique_id}' already exists.")


def custom_mongodb_processing(mongodb_srv, scrapped_chunks, prefix, indices, kbId, content_type, title, unique_id,
                              customdb_name, url=None):
    custom_collection = connect_custom_mongodb(mongodb_srv, customdb_name)
    insert_content(all_chunks=scrapped_chunks, kbId=kbId, custom_collection=custom_collection, unique_id=unique_id,
                   url=url)

    content_dict = {}
    for doc in custom_collection.find({"unique_id": unique_id}, {"content": 1}):
        if 'content' in doc:
            content_dict[doc['_id']] = prefix + doc['content']

    # Generate embeddings for all contents
    content_chunks = list(content_dict.values())  # Extract all content as a list
    embeddings, execution_time_embeddings = runpod_api_pipeline(
        substrings=content_chunks,
        query='',
        top_k=5,
        threshold=30,
        task='embeddings',
        embedings=True
    )

    # Construct a dictionary with _id as key and embeddings as value
    embedding_dict = {key: embeddings[i] for i, key in enumerate(content_dict.keys())}

    insert_content(all_chunks=content_chunks, indices=indices, embedding_dict=embedding_dict, kbId=kbId, url=url,
                   content_type=content_type, title=title, default_db=True)

    return execution_time_embeddings


def insert_content(all_chunks=None, indices=None, embedding_dict=None, kbId=None, url=None, content_type=None,
                   title=None, default_db=False, custom_collection=None, unique_id=None):
    if default_db:
        default_collection = default_mongodb['document-kb']
        documents_default_db = []

        for i, obj_id in enumerate(embedding_dict.keys()):
            # Check if all required data exists
            if i < len(indices):
                document = {
                    "datetime": datetime.datetime.now(),
                    "type": content_type,
                    "title": title,
                    "url": url,
                    "kbId": kbId,
                    "reference_to_user_db": obj_id,
                    "metadata": {
                        "pageNo": indices[i].get('page_no', None),
                        "chunkNo": indices[i].get('chunk_no', None)
                    },
                    "bgeVectors": embedding_dict[obj_id]
                }
                documents_default_db.append(document)
            else:
                logger.info(f"Skipping entry for obj_id {obj_id} due to missing data.")

        # Insert documents into the collection
        if documents_default_db:
            try:
                default_collection.insert_many(documents_default_db)
                logger.info("Documents inserted successfully.")
            except Exception as e:
                logger.error(f"Error inserting documents: {e}")

    else:
        existing_document = custom_collection.find_one({"unique_id": unique_id})
        if existing_document:
            raise ValueError(f"Document with unique_id '{unique_id}' already exists.")
        documents_custom_db = [{
            "datetime": datetime.datetime.now(),
            "kbId": kbId,
            "url": url,
            "unique_id": unique_id,
            "content": all_chunks[i]
        } for i in range(len(all_chunks))]

        custom_collection.insert_many(documents_custom_db)
        logger.info("Documents inserted successfully in Custom MongoDB.")
