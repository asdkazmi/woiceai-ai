import json
import logging
import os
import time
import boto3
from queue import Queue

from modules import chunks, reading
from modules.credits import cost
from modules.custom_mongodb_pipeline import custom_mongodb_processing, check_unique_id, delete_documents
from modules.embeddings import runpod_api_pipeline
from modules.mongo import db
from modules.mongo import insert_documents, insert_text
from modules.s3download import download_file_from_s3
from modules.sns import sending_message_attributes_to_sns

logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    handler_start = time.time()
    data = json.loads(event.get("body", json.dumps(event)).strip())
    file_type = ""
    file_path = ""
    s3_key = None
    audio_urls = ""
    audio_s3_key = ""
    image_s3_key = ""
    video_s3_key = ""
    text_id = None
    text = ""
    url = ""
    Id = ""
    req_data = data['Records'][0]['Sns']
    access_key = os.environ.get("ACCESS_KEY")
    secret_key = os.environ.get("SECRET_KEY")
    content = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.CONTENT', {}).get('Value', None)
    text = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.TEXT', {}).get('Value', None)
    content_type = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.CONTENT_TYPE', {}).get('Value', None)
    kbId = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.ID', {}).get('Value', None)
    flag = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.ACTION', {}).get('Value', None)
    title = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.TITLE', {}).get('Value', None)
    mongodb_srv_id = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.MONGODB_SRV_ID', {}).get('Value', None)
    unique_id = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.UNIQUE_ID', {}).get('Value', None)

    mongodb_srv = None
    if mongodb_srv_id:
        keys_collection = db["keys"]
        document = keys_collection.find_one({'id': mongodb_srv_id})
        if document:
            mongodb_srv = document.get("mongodb_srv")
            logger.info(f"Fetched mongodb_srv: {mongodb_srv}")

            if flag == "ADD_FILE":
                try:
                    # Check if the unique_id exists
                    check_unique_id(mongodb_srv=mongodb_srv, unique_id=unique_id)
                except ValueError as e:
                    logger.error(str(e))  # Log the error
                    raise  # Re-raise the error to handle it in the calling code
        else:
            raise Exception(f"mongodb_srv with id {mongodb_srv_id} not found.")

    if content_type == "file":
        s3_key = content
    elif content_type == "text":
        text_id = content
    elif content_type == "audio":
        audio_s3_key = content
    elif content_type == "image":
        image_s3_key = content
    elif content_type == "video":
        video_s3_key = content
    elif content_type == "url":
        url = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.CONTENT', {}).get('Value', None)

    if flag == "ADD_FILE" and s3_key:
        file_path, Id = download_file_from_s3(s3_key)

    if not kbId:
        message_attributes = {
            'KNOWLEDGEBASE.STATUS': {'DataType': 'String', 'StringValue': "Failed"},
            'body': {'DataType': 'String', 'StringValue': json.dumps({'message': 'kbId is required'})},
            'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
        }
        sending_message_attributes_to_sns(message_attributes)
        return {'KNOWLEDGEBASE.STATUS': "Failed", 'body': json.dumps({'message': 'kbId is required'})}

    logger.info("Api called!!!")
    # call sns for processing here and return status : "processing"
    if flag == "DELETE_KNOWLEDGEBASE":
        message_attributes = {
            "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
            "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Processing"},
            "KNOWLEDGEBASE.ACTION": {'DataType': 'String', 'StringValue': "DELETE_KNOWLEDGEBASE"},
            "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"}
        }
    else:
        message_attributes = {
            "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
            "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
            "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
            "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Processing"},
            'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
        }
    sending_message_attributes_to_sns(message_attributes)

    if (flag == "ADD_FILE" and s3_key) or (flag == "ADD_FILE" and text_id):
        try:
            if s3_key:
                if not file_path.lower().endswith(('.pdf', '.docx', '.txt')):
                    raise ValueError(f"Unsupported file format: {os.path.basename(file_path)}")

                if file_path.lower().endswith('.pdf'):
                    text_data = reading.read_pdf_file(file_path)
                    text = [data['content'] for data in text_data]
                    file_type = "pdf"
                elif file_path.lower().endswith('.docx'):
                    text = reading.read_docx_file(file_path)
                    file_type = "docx"
                elif file_path.lower().endswith('.txt'):
                    text = reading.read_text_file(file_path)
                    file_type = "txt"
            logger.info("Creating chunks")
            all_data = chunks.split_text_into_chunks(content=text)
            document_chunks = all_data.get("chunks")
            prefix = f"File Type: {file_type}; File Name: {title}: "

            if mongodb_srv:
                execution_time_embeddings = custom_mongodb_processing(document_chunks=document_chunks,
                                                                      mongodb_srv=mongodb_srv, unique_id=unique_id,
                                                                      prefix=prefix, s3key=s3_key,
                                                                      indices=all_data.get("indices"), kbId=kbId,
                                                                      content_type=content_type, title=title)

                handler_end = time.time()
                handler_duration = handler_end - handler_start
                credits_consumed = cost(handler_duration, execution_time_embeddings)
                logger.info(f"Successfully processed: {os.path.basename(file_path)}")
                message_attributes = {
                    "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                    "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
                    "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                    "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Completed"},
                    "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": str(credits_consumed)},
                    'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
                }
                sending_message_attributes_to_sns(message_attributes)
                return message_attributes

            updated_document_chunks = [prefix + item for item in document_chunks]
            logger.info("Creating Embeddings")
            embeddings, execution_time_embeddings = runpod_api_pipeline(substrings=updated_document_chunks, query='',
                                                                        top_k=5,
                                                                        threshold=30,
                                                                        task='embeddings', embeddings=True)
            logger.info("Uploading to DB")

            if s3_key:
                insert_documents(all_data.get("chunks"), all_data.get("indices"), embeddings, kbId,
                                 s3_key, Id, content_type, title)
            else:
                insert_text(all_data.get("chunks"), all_data.get("indices"), embeddings, kbId,
                            text_id, content_type, title)

            logger.info("Text extraction completed!!!")
            if s3_key:
                os.remove(file_path)

            handler_end = time.time()
            handler_duration = handler_end - handler_start
            credits_consumed = cost(handler_duration, execution_time_embeddings)
            logger.info(f"Successfully processed: {os.path.basename(file_path)}")
            message_attributes = {
                "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
                "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Completed"},
                "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": str(credits_consumed)},
                'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
            }
            sending_message_attributes_to_sns(message_attributes)
            return message_attributes
        except Exception as e:
            print(e)
            message_attributes = {
                "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
                "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Failed"},
                "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
            }
            sending_message_attributes_to_sns(message_attributes)
            return message_attributes

    elif flag == "ADD_FILE" and audio_s3_key:
        try:
            result = runpod_api_pipeline(audio_s3_key=audio_s3_key, kbId=kbId, content_type=content_type, title=title,
                                         mongodb_srv=mongodb_srv, unique_id=unique_id)
            return result

        except Exception as e:
            logger.error(f"Error transcribing audio file: {e}")
            message_attributes = {
                "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
                "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Failed"},
                "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
            }
            sending_message_attributes_to_sns(message_attributes)
            return message_attributes

    elif flag == "ADD_FILE" and image_s3_key:
        try:
            result = runpod_api_pipeline(image_s3_key=image_s3_key, kbId=kbId, content_type=content_type, title=title,
                                         mongodb_srv=mongodb_srv, unique_id=unique_id)
            return result
        except Exception as e:
            logger.error(f"Error : {e}")

    elif flag == "ADD_FILE" and video_s3_key:
        try:
            result = runpod_api_pipeline(video_s3_key=video_s3_key, kbId=kbId, content_type=content_type, title=title,
                                         mongodb_srv=mongodb_srv, unique_id=unique_id)
            return result
        except Exception as e:
            logger.error(f"Error : {e}")


    elif flag == "ADD_FILE" and url:
        logger.info("Processing url")
        scrapper_lambda_arn = os.environ.get("SCRAPPER_LAMBDA_ARN")
        client = boto3.client('lambda', aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name='us-east-1')
        depth = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.URL_DEPTH', {}).get('Value', 0)
        if int(depth) == 0:
            payload = {
                "KBID": kbId,
                "CONTENT": {
                    "url": url,
                    "depth": int(depth)
                },
                "CONTENT_TYPE": "url",
                "UNIQUE_ID": unique_id
            }
            message = client.invoke(FunctionName=scrapper_lambda_arn, InvocationType='RequestResponse',
                                    Payload=json.dumps(payload))
            response_payload = json.loads(message['Payload'].read())
            message_attributes = {
                "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
                "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                "KNOWLEDGEBASE.STATUS": {"DataType": "String",
                                         "StringValue": response_payload.get("KNOWLEDGEBASE.STATUS", {}).get('StringValue', 'FAILED')},
                'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
            }
            sending_message_attributes_to_sns(message_attributes)
            return {'statusCode': 200, 'message': 'Scrapper triggered successfully',
                    'lambda_response': response_payload}
        else:
            tree_document_id = None
            url_queue = Queue()
            url_queue.put((url, int(depth), None))
            while not url_queue.empty():
                current_url, current_depth, parent_url = url_queue.get()
                payload = {
                    "KBID": kbId,
                    "CONTENT": {
                        "url": current_url,
                        "parent_url": parent_url,
                        "depth": current_depth,
                        "tree_document_id": tree_document_id
                    },
                    "CONTENT_TYPE": "url",
                    "UNIQUE_ID": unique_id
                }
                message = client.invoke(
                    FunctionName=scrapper_lambda_arn,
                    InvocationType="RequestResponse",  # Can be 'Event' for async, 'RequestResponse' for sync
                    Payload=json.dumps(payload),
                )
                response_payload = json.loads(message['Payload'].read())
                if tree_document_id is None:
                    tree_document_id = response_payload.get("KNOWLEDGEBASE.TREE_DOCUMENT_ID", {}).get('StringValue', None)
                if current_depth > 0:
                    all_urls = response_payload.get("KNOWLEDGEBASE.URL_DEPTH", {}).get('StringValue', [])
                    if all_urls:
                        for url in all_urls:
                            url_queue.put((url, current_depth - 1, current_url))
            message_attributes = {
                "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
                "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Completed" if tree_document_id else "Failed"},
                'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
            }
            sending_message_attributes_to_sns(message_attributes)
            return {'statusCode': 200, 'message': 'Scrapper triggered successfully'}


    elif flag == "DELETE_FILE":
        try:
            if content_type == "video" or content_type == "file" or content_type == "image" or content_type=="text":
                s3_key = content
                db['document-kb'].delete_many({"s3_Key": s3_key, "kbId": kbId})
                message = f"Successfully deleted document with Id: {s3_key}"
                logger.info(message)
                message_attributes = {
                    "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                    "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
                    "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                    "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Completed"},
                    "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                    'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
                }
                sending_message_attributes_to_sns(message_attributes)
                return message_attributes
            elif content_type == "audio":
                audio_url = content
                db['document-kb'].delete_many({"audio_url": audio_url, "kbId": kbId})
                message = f"Successfully deleted document with Id: {audio_url}"
                logger.info(message)
                message_attributes = {
                    "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                    "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
                    "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                    "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Completed"},
                    "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                    'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
                }
                sending_message_attributes_to_sns(message_attributes)
                return message_attributes
            elif content_type == "url":
                tree_document = db["tree-of-urls"].find_one({"url": url, "kbId": kbId})
                if tree_document:
                    tree_document_id = tree_document.get('_id')
                    db['document-kb'].delete_many({"tree_document_id": str(tree_document_id)})
                    db["tree-of-urls"].delete_many({"_id": tree_document_id})
                else:
                    db['document-kb'].delete_many({"url": url, "kbId": kbId})
                message = f"Successfully deleted document with Id: {url}"
                logger.info(message)
                message_attributes = {
                    "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                    "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
                    "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                    "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Completed"},
                    "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                    'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
                }
                sending_message_attributes_to_sns(message_attributes)
                return message_attributes
        except Exception as e:
            logger.info(e)
            message_attributes = {
                "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                "KNOWLEDGEBASE.CONTENT": {"DataType": "String", "StringValue": content},
                "KNOWLEDGEBASE.CONTENT_TYPE": {"DataType": "String", "StringValue": content_type},
                "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Failed"},
                "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                'KNOWLEDGEBASE.UNIQUE_ID': {'DataType': 'String', 'StringValue': unique_id}
            }
            sending_message_attributes_to_sns(message_attributes)
            return message_attributes

    elif flag == "DELETE_KNOWLEDGEBASE":
        try:
            db['document-kb'].delete_many({"kbId": kbId})
            db['restricted-queries'].delete_many({"kbId": kbId})
            db['schema-based-kb'].delete_many({"kbId": kbId})
            db['tree-of-urls'].delete_many({"kbId": kbId})
            db['keys'].delete_many({"kbId": kbId})
            db['conversation-history'].delete_many({"kbId": kbId})
            message = "Successfully deleted the KnowledgeBase"
            logger.info(message)
            message_attributes = {
                "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Completed"},
                "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                "KNOWLEDGEBASE.ACTION": {'DataType': 'String', 'StringValue': "DELETE_KNOWLEDGEBASE"}
            }
            sending_message_attributes_to_sns(message_attributes)
            return message_attributes
        except Exception as e:
            logger.info(e)
            message_attributes = {
                "KNOWLEDGEBASE.ID": {"DataType": "String", "StringValue": kbId},
                "KNOWLEDGEBASE.STATUS": {"DataType": "String", "StringValue": "Failed"},
                "KNOWLEDGEBASE.CREDITS_CONSUMED": {"DataType": "String", "StringValue": "0"},
                "KNOWLEDGEBASE.ACTION": {'DataType': 'String', 'StringValue': "DELETE_KNOWLEDGEBASE"}
            }
            sending_message_attributes_to_sns(message_attributes)
            return message_attributes
