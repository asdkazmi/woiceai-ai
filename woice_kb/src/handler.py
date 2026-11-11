import os
import json
import logging
import time
import boto3

logger = logging.getLogger(__name__)
from modules import chunks, reading
from modules.mongo import insert_documents, insert_audio
from modules.mongo import db
from modules.embedings import runpod_api_pipeline
from modules.s3download import download_file_from_s3
from modules.credits import cost


def lambda_handler(event, context):
    handler_start = time.time()
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

    file_path = ""
    s3_key = ""
    audio_urls = ""
    url = ""
    Id = ""
    access_key = os.environ.get("ACCESS_KEY")
    secret_key = os.environ.get("SECRET_KEY")
    content = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.CONTENT', {}).get('StringValue', None)
    content_type = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.CONTENT_TYPE', {}).get('StringValue', None)
    kbId = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.ID', {}).get('StringValue', None)
    flag = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.ACTION', {}).get('StringValue', None)

    if content_type == "file":
        s3_key = content
    elif content_type == "audio":
        audio_urls = [content]
    elif content_type == "url":
        url = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.CONTENT', {}).get('StringValue', None).get(
            'url', None)
        depth = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.CONTENT', {}).get('StringValue', None).get(
            'depth', None)

    if s3_key:
        file_path, Id = download_file_from_s3(s3_key)

    if not kbId:
        return {'KNOWLEDGEBASE.STATUS': "Failed", 'body': json.dumps({'message': 'kbId is required'})}

    logger.info("Api called!!!")
    # call sns for processing here and return status : "processing"

    if flag == "ADD_FILE" and s3_key:
        try:
            if not file_path.lower().endswith(('.pdf', '.docx', '.txt')):
                raise ValueError(f"Unsupported file format: {os.path.basename(file_path)}")

            if file_path.lower().endswith('.pdf'):
                text_data = reading.read_pdf_file(file_path)
                text = [data['content'] for data in text_data]

            elif file_path.lower().endswith('.docx'):
                text = reading.read_docx_file(file_path)

            elif file_path.lower().endswith('.txt'):
                text = reading.read_text_file(file_path)
            logger.info("Creating chunks")
            all_data = chunks.split_text_into_chunks(content=text)
            logger.info("Creating Embeddings")
            embeddings, execution_time_embeddings = runpod_api_pipeline(substrings=all_data.get("chunks"), query='',
                                                                        top_k=5,
                                                                        threshold=30,
                                                                        task='embeddings', embedings=True)
            logger.info("Uploading to DB")
            insert_documents(all_data.get("chunks"), all_data.get("indices"), embeddings, kbId,
                             s3_key, Id, content_type)

            logger.info("Text extraction completed!!!")
            os.remove(file_path)

            handler_end = time.time()
            handler_duration = handler_end - handler_start
            credits_consumed = cost(handler_duration, execution_time_embeddings)
            logger.info(f"Successfully processed: {os.path.basename(file_path)}")
            return {'KNOWLEDGEBASE.STATUS': "Completed", 'KNOWLEDGEBASE.ID ': kbId,
                    "KNOWLEDGEBASE.CONTENT": {"credit_consumed": credits_consumed},
                    'KNOWLEDGEBASE.CONTENT_TYPE': content_type}
        except Exception as e:
            print(e)
            return {'KNOWLEDGEBASE.STATUS': "Failed", 'message': json.dumps({'error': f'{e}'})}

    elif flag == "DELETE_FILE":
        try:
            result = db['chunks'].delete_many({"Id": Id})
            if result.deleted_count > 0:
                message = f"Successfully deleted document with Id: {Id} for KB: {kbId}"
                logger.info(message)
                return {'KNOWLEDGEBASE.STATUS': "Completed", 'body': json.dumps({'message': message})}
            else:
                message = f"No document found with Id: {Id} for KB: {kbId}"
                logger.info(message)
                return {'KNOWLEDGEBASE.STATUS': "Failed", 'body': json.dumps({'message': message})}
        except Exception as e:
            logger.info(e)
            return {'KNOWLEDGEBASE.STATUS': "Failed", 'body': json.dumps({'error': f'{e}'})}

    elif flag == "DELETE_KNOWLEDGEBASE":
        try:
            db['chunks'].drop()
            message = "Successfully dropped the chunks collection"
            logger.info(message)
            return {'KNOWLEDGEBASE.STATUS': "Completed", 'body': json.dumps({'message': message})}
        except Exception as e:
            logger.info(e)
            return {'KNOWLEDGEBASE.STATUS': "Failed", 'body': json.dumps({'error': f'{e}'})}

    elif flag == "ADD_FILE" and audio_urls:
        try:
            response, execution_time_transcriber = runpod_api_pipeline(audio_urls=audio_urls)
            transcript = response.get("transcription")[0][0].get("text")
            logger.info("Audio file transcribed successfully")

            logger.info("Converting transcript to chunks")
            all_data = chunks.split_text_into_chunks(content=transcript)

            logger.info("Creating embeddings for chunks")
            embeddings, execution_time_embeddings = runpod_api_pipeline(substrings=all_data.get("chunks"), query='',
                                                                        top_k=5,
                                                                        threshold=30,
                                                                        task='embeddings', embedings=True)

            insert_audio(all_data.get("chunks"), all_data.get("indices"), embeddings, kbId, audio_urls)
            handler_end = time.time()
            handler_duration = handler_end - handler_start
            credits_consumed = cost(handler_duration, execution_time_embeddings, execution_time_transcriber)
            return {'KNOWLEDGEBASE.STATUS': "Completed", "KNOWLEDGEBASE.ID": kbId,
                    'KNOWLEDGEBASE.CONTENT': {"Transcription": transcript, "credits_consumed": credits_consumed},
                    'KNOWLEDGEBASE.CONTENT_TYPE': content_type}

        except Exception as e:
            logger.error(f"Error transcribing audio file: {e}")
            return {'KNOWLEDGEBASE.STATUS': "Failed",
                    'message': json.dumps({'error': f'Error transcribing audio file: {e}'})}


    elif url:
        sns_topic_arn = 'arn:aws:sns:us-east-1:471112754613:woice-ai-knowledgebase'
        sns_client = boto3.client('sns', aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                                  region_name='us-east-1')
        payload = {
            'url': url,
            'kbId': kbId,
            'content_type': content_type,
            'depth': depth
        }
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=json.dumps(payload)
        )
        return {'KNOWLEDGEBASE.STATUS': "Processing", 'message': 'Message sent to SNS topic successfully'}
