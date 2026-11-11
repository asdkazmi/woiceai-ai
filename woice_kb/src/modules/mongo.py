import datetime
import logging
import os

from dotenv import load_dotenv
from pymongo import MongoClient

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


def insert_documents(all_chunks, indices, embeddings, kbId, s3_key, Id, content_type, title):
    # Prepare documents for insertion
    documents = [{
        "datetime": datetime.datetime.now(),
        "type": content_type,
        "title": title,
        "s3_Key": s3_key,
        "kbId": kbId,
        "Id": Id,
        "metadata": {"pageNo": indices[i]['page_no'], "chunkNo": indices[i]['chunk_no']},
        "content": all_chunks[i],
        "bgeVectors": embeddings[i]
    } for i in range(len(all_chunks))]

    # Insert documents into the collection
    collection.insert_many(documents)


def insert_text(all_chunks, indices, embeddings, kbId, s3_key, content_type, title):
    # Prepare documents for insertion
    documents = [{
        "datetime": datetime.datetime.now(),
        "type": content_type,
        "title": title,
        "s3_Key": s3_key,
        "kbId": kbId,
        "metadata": {"chunkNo": indices[i]['chunk_no']},
        "content": all_chunks[i],
        "bgeVectors": embeddings[i]
    } for i in range(len(all_chunks))]

    # Insert documents into the collection
    collection.insert_many(documents)
