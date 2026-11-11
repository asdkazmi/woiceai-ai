import logging

from pymongo import MongoClient, errors

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def connect_custom_mongodb(db, mongodb_srv_id, customdb_name):
    try:
        mongodb_srv = fetch_mongodb(db, mongodb_srv_id)
        custom_client = MongoClient(mongodb_srv)

        # Send a ping to confirm a successful connection
        custom_client.admin.command('ping')
        logger.info("Pinged your deployment. You successfully connected to MongoDB!")

        custom_db = custom_client[customdb_name]
        return custom_db
    except errors.PyMongoError as e:
        logger.error(f"Error connecting to MongoDB: {e}")
        raise


def fetch_mongodb(db, mongodb_srv_id):
    if mongodb_srv_id:
        keys_collection = db["keys"]
        document = keys_collection.find_one({'id': mongodb_srv_id})
        if document:
            mongodb_srv = document.get("mongodb_srv")
            logger.info(f"Fetched mongodb_srv: {mongodb_srv}")
            return mongodb_srv
        else:
            raise Exception(f"Document with id {mongodb_srv_id} not found.")
