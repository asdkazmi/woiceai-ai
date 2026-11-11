from pymongo import MongoClient
import datetime
from dotenv import load_dotenv
import os
import re

load_dotenv()

uri = os.getenv('DB_URI')

client = MongoClient(uri)

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

# Access the 'Woice' database and the 'chunks' collection
db = client['woice']

collection_con = db['conversation']


def store_conversation(user_id, user_query, llm_response, kbId):
    """
    This function stores a new conversation entry in the database.It finds the document with the given user_id and
    appends a new conversation entry to the existing conversation. If the document does not exist, it creates a new
    document with the given user_id and conversation entry.
    :param user_id:
    :param user_query:
    :param llm_response:
    :return:
    """
    # Find the document with the given user_id
    document = collection_con.find_one({"user_id": user_id})

    # Create a new conversation entry
    new_entry = {
        "datetime": datetime.datetime.now(),
        "human:": user_query,
        "ai:": llm_response
    }

    if document:
        # Append the new entry to the existing conversation
        collection_con.update_one(
            {"user_id": user_id},
            {"$push": {"conversations": new_entry}}
        )
    else:
        # Create a new document for a new user_id
        new_document = {
            "user_id": user_id,
            "kbId": kbId,
            "conversations": [new_entry]
        }
        collection_con.insert_one(new_document)
    # print(collection_con.find_one({"user_id": user_id}))

# def retrieve_conversation(user_id):
#     """
#     This function retrieves a conversation history for a given user_id. It finds the document with the given user_id
#     and
#     returns the conversation history. If the document does not exist, it returns None.
#     :param user_id:
#     :return:
#     """
#     # Find the document with the given user_id
#     document = collection_con.find_one({"user_id": user_id})
#
#     if document:
#         print(document["conversations"])
#         return document["conversations"]
#     else:
#         return None
#
#
# def retrieve_latest_conversation(user_id):
#     document = collection_con.find_one({"user_id": user_id})
#     if document:
#         conversations = document["conversations"]
#         all_text = ''
#         for conversation in conversations:
#             all_text += conversation['human:'] + ' ' + conversation['ai:']
#             words = all_text.split()
#         # words = re.findall(r'\b\w+\b', all_text)
#         last_3000_words = words[-3000:] if len(words) >= 3000 else words[:]
#         print("3k", last_3000_words)
#         return ''.join(last_3000_words)
#     else:
#         return None
