import json
import logging
import os
import time
import traceback
from sys import exc_info
from bson import ObjectId
from pymongo import MongoClient

from modules import chunks
from modules.credits import cost
from modules.embeddings import runpod_api_pipeline
from modules.mongo import insert_documents, get_total_scrapped
from modules.seleniumCode import process_urls_with_threading, process_url
from modules.sns import sending_message_attributes_to_sns
from modules.filtering_urls import filter_urls

logger = logging.getLogger()
logger.setLevel(logging.INFO)
uri = os.getenv('DB_URI')
# Create a new client and connect to the server
client = MongoClient(uri)
db = client['woice-ai-kb']
collection = db['document-kb']
urls_tree_collection = db['tree-of-urls']

def scrapper(event, context):
    handler_start = time.time()
    unique_id = None
    tree_document_id = None
    try:
        data = json.loads(event.get("body", json.dumps(event)).strip())
        if "Records" in data:
            req_data = data['Records'][0]['Sns']
            req_data = json.loads(req_data)
            logger.info("Sns event")
            logger.info(f"sns req_data: {req_data}")
            logger.info(f"sns req_data data type: {type(req_data)}")
        else:
            req_data = data
            logger.info(f"api gateway req_data: {req_data}")
            logger.info(f"api gateway req_data data type: {type(req_data)}")

        unique_id = req_data.get('UNIQUE_ID', None)
        return_just_content = req_data.get('RETURN_CONTENT_ONLY', False)
        if return_just_content:
            logger.info("Request received for just Scrapping")
            urls = req_data.get('CONTENT', {}).get('urls', [])
            depth = req_data.get('CONTENT', {}).get('depth', 0)
            total_scrapped_data = {}
            for url in urls:
                scrapped_data, failed_urls = process_urls_with_threading([url])
                total_scrapped_data.update(scrapped_data)
            logger.info('Returning scrapped content')
            return total_scrapped_data
        else:
            url = req_data.get('CONTENT', {}).get('url', None)
            parent_url = req_data.get('CONTENT', {}).get('parent_url', None)
            tree_document_id = req_data.get('CONTENT', {}).get('tree_document_id', None)
            content_type = req_data.get('CONTENT_TYPE', None)
            kbId = req_data.get('KBID', None)
            depth = req_data.get('CONTENT', {}).get('depth', 0)
            logger.info("Processing")

            if not kbId:
                message_attributes = {
                    'KNOWLEDGEBASE.STATUS': {'DataType': 'String', 'StringValue': "Failed"},
                    'body': {'DataType': 'String', 'StringValue': json.dumps({'message': 'kbId is required'})},
                    'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}

                }
                sending_message_attributes_to_sns(message_attributes)
                return {
                    "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Failed"},
                    'body': json.dumps({'message': 'kbId is required'})
                }

        try:
            scrapped_data, crawled_urls, failed_urls = process_urls_with_threading([url])
            if not scrapped_data:
                if tree_document_id:
                    urls_tree_collection.update_one(
                        {"_id": ObjectId(tree_document_id)},
                        {'$push': {'tree': {"parent_url": parent_url, "url": url, "scrapped": False}}}
                    )
                    scrapped_status = get_total_scrapped(tree_document_id=tree_document_id)
                    message_attributes = {
                        "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": str(kbId)},
                        "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": url},
                        "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                        "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                        'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id},
                        **scrapped_status
                    }
                    sending_message_attributes_to_sns(message_attributes)
                    return message_attributes
                else:
                    message_attributes = {
                        "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": str(kbId)},
                        "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": url},
                        "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                        "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Failed"},
                        "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                        'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
                    }
                    sending_message_attributes_to_sns(message_attributes)
                    return message_attributes


            logger.info("Creating chunks")
            all_data = chunks.split_text_into_chunks(content=scrapped_data.get(url))
            scrapped_chunks = all_data.get("chunks")
            page_title = process_url(url, return_just_title=True)
            prefix = f"Content Type: URL; URL page title: {page_title} : "
            updated_scrapped_chunks = [prefix + item for item in scrapped_chunks]
            logger.info("Creating Embeddings")
            embeddings, execution_time = runpod_api_pipeline(substrings=updated_scrapped_chunks, query='', top_k=5,
                                                             threshold=30,
                                                             task='embeddings', embedings=True)
            if tree_document_id:
                urls_tree_collection.update_one(
                    {"_id": ObjectId(tree_document_id)},
                    {'$push': {'tree': {"parent_url": parent_url, "url": url, "scrapped": True}}}
                )
                logger.info(f"Updated tree of urls with url: {url} and parent url: {parent_url}")
            elif depth > 0:
                document = {
                    "url": url,
                    "kbId": kbId
                }
                result = urls_tree_collection.insert_one(document)
                tree_document_id = result.inserted_id
                tree_document_id = str(tree_document_id)
                message_attributes = {
                    "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                    "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": url},
                    "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                    'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id},
                    'KNOWLEDGEBASE.TREE_DOCUMENT_ID': {'DataType': 'String', 'StringValue': tree_document_id}
                }
                sending_message_attributes_to_sns(message_attributes)
                logger.info(f"Inserted url into tree of urls as base url: {url}")
            else:
                insert_documents(all_chunks=all_data.get("chunks"), indices=all_data.get("indices"), url=url,
                                 embeddings=embeddings, kbId=kbId, content_type=content_type, title=page_title)
                handler_end = time.time()
                handler_duration = handler_end - handler_start
                credits_consumed = cost(handler_duration, execution_time)
                message_attributes = {
                    "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": str(kbId)},
                    "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": url},
                    "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                    "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": str(credits_consumed)},
                    "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Completed"},
                    'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
                }
                return message_attributes
            insert_documents(all_chunks=all_data.get("chunks"), indices=all_data.get("indices"), url=url,
                             embeddings=embeddings, kbId=kbId, content_type=content_type, title=page_title,
                             tree_document_id=tree_document_id)
            logger.info("Text extraction completed!!!")

            handler_end = time.time()
            handler_duration = handler_end - handler_start
            credits_consumed = cost(handler_duration, execution_time)
            scrapped_status = get_total_scrapped(tree_document_id=tree_document_id)
            message_attributes = {
                "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": str(kbId)},
                "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": url},
                "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                **scrapped_status,
                "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": str(credits_consumed)},
                'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
            }
            sending_message_attributes_to_sns(message_attributes)

            if depth > 0:
                logger.info("Filtering URLs...")
                filtered_urls = filter_urls(url, crawled_urls, depth)
                handler_end = time.time()
                handler_duration = handler_end - handler_start
                credits_consumed = cost(handler_duration, execution_time)
                return {
                    "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                    "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": url},
                    "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                    "KNOWLEDGEBASE.URL_DEPTH": {"DataType": "String", "StringValue": filtered_urls},
                    "KNOWLEDGEBASE.TREE_DOCUMENT_ID": {"DataType": "String", "StringValue": tree_document_id},
                    "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": credits_consumed},
                }

            else:
                handler_end = time.time()
                handler_duration = handler_end - handler_start
                credits_consumed = cost(handler_duration, execution_time)
                message_attributes = {
                    "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": str(kbId)},
                    "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": url},
                    "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                    "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": str(credits_consumed)},
                    'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
                }
                sending_message_attributes_to_sns(message_attributes)
                return message_attributes
        except Exception as e:
            logger.error(str(e))
            message_attributes = {
                "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": str(kbId)},
                "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": url},
                "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
            }
            if tree_document_id:
                scrapped_status = get_total_scrapped(tree_document_id=tree_document_id)
                message_attributes.update(scrapped_status)
            sending_message_attributes_to_sns(message_attributes)
            return message_attributes
    except AssertionError:
        logger.error(traceback.format_exc())
        message_attributes = {
            'body': {'DataType': 'String', 'StringValue': json.dumps({'error': f"{exc_info()[1]}"})},
            'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
        }
        if tree_document_id:
            scrapped_status = get_total_scrapped(tree_document_id=tree_document_id)
            message_attributes.update(scrapped_status)
        sending_message_attributes_to_sns(message_attributes)
        return {
            "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Failed"},
            'body': {
                'error': f"{exc_info()[1]}"
            }
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        message_attributes = {
            'body': {'DataType': 'String', 'StringValue': json.dumps(
                {'error': f"{str(exc_info()[0]).split('class')[1].split('>')[0].strip()}: {exc_info()[1]}"})},
            'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
        }
        if tree_document_id:
            scrapped_status = get_total_scrapped(tree_document_id=tree_document_id)
            message_attributes.update(scrapped_status)
        sending_message_attributes_to_sns(message_attributes)
        return {
            "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Failed"},
            'body': {
                'error': f"{str(exc_info()[0]).split('class')[1].split('>')[0].strip()}: {exc_info()[1]}"
            }
        }
