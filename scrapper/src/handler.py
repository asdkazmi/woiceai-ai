import json
import logging
import traceback
import time
from sys import exc_info
from modules import chunks
from modules.mongo import insert_documents
from modules.embedings import runpod_api_pipeline
from modules.web import WebCrawler
from modules.seleniumCode import process_urls_with_threading
from modules.credits import cost

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def scrapper(event, context):
    handler_start = time.time()
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

        url = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.CONTENT', {}).get('StringValue', None).get('url',
                                                                                                                  None)
        content_type = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.CONTENT_TYPE', {}).get('StringValue',
                                                                                                       None)
        kbId = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.ID', {}).get('StringValue', None)
        depth = req_data.get('MessageAttributes', {}).get('KNOWLEDGEBASE.CONTENT', {}).get('StringValue', None).get(
            'depth', None)
        logger.info("Processing")
        crawler = WebCrawler(url)

        if not kbId:
            return {'KNOWLEDGEBASE.STATUS': "Failed", 'body': json.dumps({'message': 'kbId is required'})}

        try:
            scrapped_data, failed_urls = process_urls_with_threading([url])
            logger.info("Creating chunks")
            all_data = chunks.split_text_into_chunks(content=scrapped_data.get(url))
            logger.info("Creating Embeddings")
            embeddings, execution_time = runpod_api_pipeline(substrings=all_data.get("chunks"), query='', top_k=5,
                                                             threshold=30,
                                                             task='embeddings', embedings=True)
            logger.info("Uploading to DB")
            insert_documents(all_data.get("chunks"), all_data.get("indices"), url, embeddings, kbId, content_type)
            logger.info("Text extraction completed!!!")

            if depth > 0:
                logger.info("Crawling URLs...")
                crawled_urls = crawler.crawl_urls(url, depth)
                handler_end = time.time()
                handler_duration = handler_end - handler_start
                credits_consumed = cost(handler_duration, execution_time)
                return {'KNOWLEDGEBASE.STATUS': "Completed", 'KNOWLEDGEBASE.ID ': kbId,
                        "KNOWLEDGEBASE.CONTENT": {'scrapped_data': scrapped_data, 'crawled_urls': crawled_urls,
                                                  "credits_consumed": credits_consumed},
                        "KNOWLEDGEBASE.CONTENT_TYPE": "url"}

            else:
                handler_end = time.time()
                handler_duration = handler_end - handler_start
                credits_consumed = cost(handler_duration, execution_time)
                return {'KNOWLEDGEBASE.STATUS': "Completed", 'KNOWLEDGEBASE.ID ': kbId,
                        "KNOWLEDGEBASE.CONTENT": {'scrapped_data': scrapped_data, "credits_consumed": credits_consumed},
                        "KNOWLEDGEBASE.CONTENT_TYPE": "url"}


        except Exception as e:
            logger.error(str(e))
            return {'KNOWLEDGEBASE.STATUS': "Failed", 'message': json.dumps({'error': str(e)})}
    except AssertionError:
        logger.error(traceback.format_exc())
        return {
            'KNOWLEDGEBASE.STATUS': "Failed",
            'body': {
                'error': f"{exc_info()[1]}"
            }
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        return {
            'KNOWLEDGEBASE.STATUS': "Failed",
            'body': {
                'error': f"{str(exc_info()[0]).split('class')[1].split('>')[0].strip()}: {exc_info()[1]}"
            }
        }
