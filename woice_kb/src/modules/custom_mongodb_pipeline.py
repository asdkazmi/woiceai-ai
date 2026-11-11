import datetime
import logging

from dotenv import load_dotenv
from pymongo import MongoClient, errors

from .embeddings import runpod_api_pipeline
from .mongo import collection as default_collection

load_dotenv()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def connect_custom_mongodb(mongodb_srv):
    try:
        uri = mongodb_srv
        custom_client = MongoClient(uri)

        # Send a ping to confirm a successful connection
        custom_client.admin.command('ping')
        logger.info("Pinged your deployment. You successfully connected to MongoDB!")

        custom_db = custom_client['woice-ai-kb']
        custom_collection = custom_db['document-kb']
        return custom_collection
    except errors.PyMongoError as e:
        logger.error(f"Error connecting to MongoDB: {e}")
        raise


def check_unique_id(mongodb_srv, unique_id):
    custom_collection = connect_custom_mongodb(mongodb_srv)
    existing_document = custom_collection.find_one({"unique_id": unique_id})
    if existing_document:
        raise ValueError(f"Document with unique_id '{unique_id}' already exists.")


def custom_mongodb_processing(mongodb_srv, document_chunks, prefix, indices, kbId, unique_id, content_type, title,
                              s3key=None):
    try:
        custom_collection = connect_custom_mongodb(mongodb_srv)

        if s3key:
            insert_content(all_chunks=document_chunks, kbId=kbId, custom_collection=custom_collection, s3_key=s3key,
                           unique_id=unique_id)
        else:
            insert_custom_text(all_chunks=document_chunks, kbId=kbId, custom_collection=custom_collection,
                               s3_key=s3key, unique_id=unique_id)

        content_dict = {}
        for doc in custom_collection.find({"unique_id": unique_id}, {"content": 1}):
            if 'content' in doc:
                content_dict[doc['_id']] = prefix + doc['content']

        # Generating embeddings for all contents
        content_chunks = list(content_dict.values())  # Extract all content as a list
        embeddings, execution_time_embeddings = runpod_api_pipeline(
            substrings=content_chunks,
            query='',
            top_k=5,
            threshold=30,
            task='embeddings',
            embeddings=True
        )

        # Constructing a dictionary with _id as key and embeddings as value
        embedding_dict = {key: embeddings[i] for i, key in enumerate(content_dict.keys())}

        if s3key:
            insert_content(indices=indices, embedding_dict=embedding_dict, kbId=kbId, s3_key=s3key,
                           content_type=content_type, title=title, default_db=True)
        else:
            insert_custom_text(indices=indices, embedding_dict=embedding_dict, kbId=kbId,
                               s3_key=s3key, content_type=content_type, title=title, default_db=True)

        return execution_time_embeddings
    except Exception as e:
        logger.error(f"Error in custom_mongodb_processing: {e}")
        raise


def insert_content(all_chunks=None, indices=None, embedding_dict=None, kbId=None, s3_key=None, content_type=None,
                   title=None, default_db=False, custom_collection=None, unique_id=None):
    try:
        if default_db:
            documents_default_db = []

            for i, obj_id in enumerate(embedding_dict.keys()):
                # Check if all required data exists
                if i < len(indices):
                    document = {
                        "datetime": datetime.datetime.now(),
                        "type": content_type,
                        "title": title,
                        "s3_Key": s3_key,
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
                except errors.PyMongoError as e:
                    logger.error(f"Error inserting documents: {e}")
        else:
            documents_custom_db = [{
                "datetime": datetime.datetime.now(),
                "kbId": kbId,
                "s3_Key": s3_key,
                "unique_id": unique_id,
                "content": all_chunks[i]
            } for i in range(len(all_chunks))]

            try:
                custom_collection.insert_many(documents_custom_db)
                logger.info("Documents inserted successfully.")
            except errors.PyMongoError as e:
                logger.error(f"Error inserting documents into custom collection: {e}")
    except Exception as e:
        logger.error(f"Error in insert_content: {e}")
        raise


def insert_custom_text(all_chunks=None, indices=None, embedding_dict=None, kbId=None, content_type=None,
                       title=None, default_db=False, custom_collection=None, s3_key=None, unique_id=None):
    try:
        if default_db:
            documents_default_db = []

            for i, obj_id in enumerate(embedding_dict.keys()):
                # Check if all required data exists
                if i < len(indices):
                    document = {
                        "datetime": datetime.datetime.now(),
                        "type": content_type,
                        "title": title,
                        "s3_Key": s3_key,
                        "kbId": kbId,
                        "reference_to_user_db": obj_id,
                        "metadata": {"chunkNo": indices[i]['chunk_no']},
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
                except errors.PyMongoError as e:
                    logger.error(f"Error inserting documents: {e}")
        else:
            documents_custom_db = [{
                "datetime": datetime.datetime.now(),
                "kbId": kbId,
                "s3_Key": s3_key,
                "unique_id": unique_id,
                "content": all_chunks[i]
            } for i in range(len(all_chunks))]

            try:
                custom_collection.insert_many(documents_custom_db)
                logger.info("Documents inserted successfully.")
            except errors.PyMongoError as e:
                logger.error(f"Error inserting documents into custom collection: {e}")
    except Exception as e:
        logger.error(f"Error in insert_custom_text: {e}")
        raise


def delete_documents(mongodb_srv, flag, kbId=None, s3key=None, audio_url=None, url=None):
    custom_collection = connect_custom_mongodb(mongodb_srv)
    if flag == "DELETE_FILE":
        if s3key:
            custom_delete = custom_collection.delete_many({"s3_Key": s3key})
            default_delete = default_collection.delete_many({"s3_Key": s3key})
            if custom_delete.deleted_count > 0 and default_delete.deleted_count > 0:
                return 1
            else:
                logger.error(f"Error in delete_documents")
        elif audio_url:
            custom_delete = custom_collection.delete_many({"audio_url": audio_url})
            default_delete = default_collection.delete_many({"audio_url": audio_url})
            if custom_delete.deleted_count > 0 and default_delete.deleted_count > 0:
                return 1
            else:
                logger.error(f"Error in delete_documents")
        elif url:
            custom_delete = custom_collection.delete_many({"url": url})
            default_delete = default_collection.delete_many({"url": url})
            if custom_delete.deleted_count > 0 and default_delete.deleted_count > 0:
                return 1
            else:
                logger.error(f"Error in delete_documents")

    elif flag == "DELETE_KNOWLEDGEBASE":
        custom_collection.delete_many({"kbId": kbId})
        default_collection.delete_many({"kbId": kbId})
