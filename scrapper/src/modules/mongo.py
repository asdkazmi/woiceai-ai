from pymongo import MongoClient
import datetime
from dotenv import load_dotenv
import os
import logging

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
db = client['woice']
collection = db['chunks']


def insert_documents(all_chunks, indices, url, embeddings, userId, kbId):
    """
    The function insert_documents connects to a MongoDB database using a provided URI, accesses a specific database and
    collection, and inserts multiple documents into the collection. Each document contains metadata such as title, datetime,
    document ID, user ID, and page/chunk numbers, as well as the actual chunk content and its corresponding embeddings.
    :param all_chunks:
    :param indices:
    :param url:
    :param embeddings:
    :param kbId:
    :param userId:
    :return:
    """

    # Prepare documents for insertion
    documents = [{
        "type": "file",
        "url": url,
        "datetime": datetime.datetime.now(),
        "kbId": kbId,
        "userId": userId,
        "metadata": {"pageNo": indices[i]['page_no'], "chunkNo": indices[i]['chunk_no']},
        "content": all_chunks[i],
        "bgeVectors": embeddings[i]
    } for i in range(len(all_chunks))]

    # Insert documents into the collection
    collection.insert_many(documents)
