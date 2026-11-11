import datetime
import logging
import os

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

logger = logging.getLogger(__name__)
load_dotenv()

uri = os.getenv('DB_URI')
# Create a new client and connect to the server
client = MongoClient(uri)

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    logger.info("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    logger.info(e)

# Access the 'Woice' database and the 'chunks' collection
db = client['woice-ai-kb']
collection = db['document-kb']


def insert_documents(all_chunks, indices, url, embeddings, kbId, content_type, title, tree_document_id=None):
    """
    The function insert_documents connects to a MongoDB database using a provided URI, accesses a specific database and
    collection, and inserts multiple documents into the collection. Each document contains metadata such as title, datetime,
    document ID, user ID, and page/chunk numbers, as well as the actual chunk content and its corresponding embeddings.
    :param tree_document_id:
    :param title:
    :param content_type:
    :param all_chunks:
    :param indices:
    :param url:
    :param embeddings:
    :param kbId:
    :return:
    """

    # Prepare documents for insertion
    tree_document_id_doc = {}
    if tree_document_id:
        tree_document_id_doc = {"tree_document_id": tree_document_id}
    documents = [{
        "type": f"{content_type}",
        "title": title,
        "url": url,
        **tree_document_id_doc,
        "datetime": datetime.datetime.now(),
        "kbId": kbId,
        "metadata": {"pageNo": indices[i]['page_no'], "chunkNo": indices[i]['chunk_no']},
        "content": all_chunks[i],
        "bgeVectors": embeddings[i]
    } for i in range(len(all_chunks))]

    # Insert documents into the collection
    collection.insert_many(documents)


def get_total_scrapped(tree_document_id):
    try:
        tree_collection = db["tree-of-urls"]
        pipeline = [
            # 1. Find the specific document by _id
            {"$match": {"_id": ObjectId(tree_document_id)}},

            # 2. Project a new field that calculates the count
            {
                "$project": {
                    "total_items": {"$size": "$tree"},
                    "total_scrapped": {
                        "$size": {
                            "$filter": {
                                "input": "$tree",
                                "as": "item",
                                "cond": {"$eq": ["$$item.scrapped", True]}
                            }
                        }
                    }
                }
            }
        ]
        result = list(tree_collection.aggregate(pipeline))
        if result:
            return {
                "KNOWLEDGEBASE.SCRAPPING_STATUS": {
                    "DataType": "String",
                    "StringValue": f"{result[0]['total_scrapped']}/{result[0]['total_items']}"}
            }
        else:
            return {}
    except Exception as e:
        logger.error(e)
        return {}