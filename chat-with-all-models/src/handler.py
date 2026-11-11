import copy
import json
import logging
import os
import torch
import re
import time
import atexit
import certifi
import numpy as np
import runpod
from dotenv import load_dotenv
from llama_cpp import Llama
from pymongo import MongoClient
from pymongo.errors import ConfigurationError

from modules.response import generate_response
from modules.llama import generate
from modules.rewrite_query import rewrite_query
from modules.fetch_custom_db import connect_custom_mongodb
from modules.stella import TextProcessor
from modules.vector import vector_search
from modules.llama_gemfilter.load_model import load_model
from modules.llama_gemfilter.my_generation import set_topk, set_select_mode, set_select_layer, reduce_layer

load_dotenv()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

retrieval = TextProcessor()

model_path = "merged-q4_k_m-model.gguf"

llama = Llama(
    model_path=model_path,  # Download the model file first
    n_ctx=8000,  # The max sequence length to use - note that longer sequence lengths require much more resources
    n_threads=8,  # The number of CPU threads to use, tailor to your system and the resulting performance
    n_gpu_layers=-1,  # The number of layers to offload to GPU, if available. -1 for offloading all layers.
)
logger.info(f"Qwen loaded")


@atexit.register
def free_model():
    llama.close()
    logger.info(f"Qwen is closed")


model_id = "Meta-Llama-3.1-8B-Instruct-gptq"
modified = "llama_gemfilter"
topk = 1024
select_layer_idx = 13
flash_attention_2 = True
model, tokenizer = load_model(model_id, modified=modified, flash_attention_2=flash_attention_2)
set_topk(model, topk, mode=modified)
set_select_mode(model, True)
select_layer_idx = set_select_layer(model, select_layer_idx)
model, original_layers = reduce_layer(model, select_layer_idx)
model = model.to("cuda")
logger.info(f"Gemfilter model loaded and transferred to {next(model.parameters()).device}")

try:
    # Establish MongoDB connection
    t = time.time()
    remote_server_uri = os.getenv('DB_URI')
    client = MongoClient(remote_server_uri, tlsCAFile=certifi.where())
    logger.info("MongoDB connection established successfully!")
    logger.info(f"MongoDB connection established in {(time.time() - t):.3f} seconds")
    db = client['woice-ai-kb']

except ConnectionError as ce:
    logger.error(f"Error connecting to MongoDB: {ce}")

except ConfigurationError as conf_err:
    logger.error(f"MongoDB configuration error: {conf_err}")

except Exception as e:
    logger.error(f"An unexpected error occurred: {e}")

logger = logging.getLogger(__name__)


def runpod_handler(event):
    try:
        handler_start = time.time()
        req_data = event['input']
        if req_data.get('task') in ['retrieval', 'embeddings']:
            return retrieval(req_data)
        user_query = req_data.get('user_query', None)
        external_knowledge_access = req_data.get('external_knowledge_access', True)
        enable_reference = req_data.get('enable_reference', False)
        kbId = req_data.get('kbId')
        history = req_data.get('history', [])
        chat_arg = req_data.get('chat_arg', {})
        temperature = chat_arg.get('temperature', 0.2)
        top_k = chat_arg.get('top_k', 40)
        top_p = chat_arg.get('top_p', 0.95)
        max_tokens = chat_arg.get('max_tokens', 2048)
        frequency_penalty = chat_arg.get('frequency_penalty', 0.0)
        presence_penalty = chat_arg.get('presence_penalty', 0.0)
        responseOnly = req_data.get('responseOnly', False)
        kb_arg = req_data.get('kb_arg', {})
        retrieval_limit = kb_arg.get('retrieval_limit', 10)
        retrieval_score = kb_arg.get('retrieval_score', 0.5)
        stop = chat_arg.get('stop', [])
        mongodb_srv_id = req_data.get('mongodb_srv_id', None)
        customdb_name = req_data.get('customdb_name', None)

        user_system_prompt = req_data.get('user_system_prompt',
                                          ("""You're Woice AI and you're here to help the people to provide the 
                                          answer based on given knowledge. Give your answer in details and utilize 
                                          more and more given information."""))

        if responseOnly:
            generated_text, total_tokens = generate(
                messages=user_query,
                kwargs={
                    "temperature": temperature,
                    "top_k": top_k,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "frequency_penalty": frequency_penalty,
                    "presence_penalty": presence_penalty
                },
                llm=llama
            )
            return generated_text, total_tokens

        custom_db = None
        if mongodb_srv_id:
            custom_db = connect_custom_mongodb(db=db, mongodb_srv_id=mongodb_srv_id, customdb_name=customdb_name)

        """
          "history": [
        {is_human: true, prompt: "How are you doing?"},
        {is_human: false, prompt: "Hi! I'm good, how are you?"}
        """
        questions_collection = db["restricted-queries"]
        documents = questions_collection.find({"kbId": int(kbId)}, {"restricted_queries": 1, "_id": 0})
        restricted_questions = []
        for doc in documents:
            restricted_questions.extend(doc.get("restricted_queries", []))  # Merge all arrays

        user_query_rr = user_query
        if history or restricted_questions:
            user_query_rr, tokens, validation_messages = rewrite_query(user_query, history, llm=llama,
                                                                    restricted_questions=restricted_questions)
            if user_query_rr in validation_messages:
                llama_response = user_query_rr
                logger.info(f"Successfully processed: {llama_response}")
                handler_end = time.time()
                handler_duration = handler_end - handler_start
                logger.info(f"Time Taken: {handler_duration:.3f} secs")
                cost = handler_duration * 1
                return {'KNOWLEDGEBASE.STATUS': "Completed",
                        "KNOWLEDGEBASE.ID ": str(kbId),
                        "KNOWLEDGEBASE.CONTENT": {'llama_response': llama_response, "total_tokens": tokens,
                                                  "cost": cost},
                        "KNOWLEDGEBASE.CONTENT_TYPE": "query"}
            logger.info(f"Rewritten Query: {user_query_rr}")
        logger.info(f"Getting relevant content")
        search_results = vector_search(collection=db["document-kb"], kbId=kbId, query=user_query_rr,
                                       limit=retrieval_limit, threshold=retrieval_score, custom_db=custom_db)
        contents = list()
        metadata_list = list()
        for i, res in enumerate(copy.deepcopy(search_results)):
            content = res.pop('content')
            _ = res.pop('score'), res.pop('kbId')
            metadata = [f'"{k}": "{v}"' for k, v in res.pop('metadata', {}).items()]
            metadata = ", ".join(metadata + [f'"{k}": "{v}"' for k, v in res.items()])
            metadata = metadata.replace('"s3_Key":', '"url":').replace('"audio_url":', '"url":')
            if '"url":' not in metadata:
                metadata = metadata + ', "url": "#"'
            content = f'CONTENTS:\n {content.strip()}\n'
            metadata_list.append(metadata)
            contents.append(content)
        sep = '-' * 20
        contents = f'\n{sep}\n\n'.join(contents)


        logger.info(f"Generating Response...")
        llama_response, total_tokens = generate_response(user_query=user_query,
                                                         contents=contents,
                                                         metadata_list=metadata_list,
                                                         history=history,
                                                         external_knowledge_access=external_knowledge_access,
                                                         temperature=temperature, top_k=top_k,
                                                         top_p=top_p,
                                                         max_tokens=max_tokens,
                                                         frequency_penalty=frequency_penalty,
                                                         presence_penalty=presence_penalty,
                                                         stop=stop,
                                                         user_system_prompt=user_system_prompt,
                                                         enable_reference=enable_reference,
                                                         model=model,
                                                         tokenizer=tokenizer,
                                                         llm=llama)
        references = {}
        if enable_reference:
            cited_references = list()
            pattern = r"\[(\d+)\]\(([^()]+)\)"
            matches = re.findall(pattern, llama_response)

            for match in matches:
                number, link = match
                cited_references.append((int(number), link))
            cited_references = list(set(cited_references))
            cited_references = sorted(cited_references, key=lambda x: x[0])
            missing_references = np.setdiff1d(range(1, len(search_results) + 1), [int(_[0]) for _ in cited_references])
            for i in sorted(missing_references, reverse=True):
                search_results.pop(i - 1)
            for i, refer in enumerate(cited_references):
                llama_response = llama_response.replace(f"[{refer[0]}]({refer[1]})", f"[{i + 1}]({refer[1]})")
            for i, res in enumerate(search_results):
                res.update(res.pop('metadata', {}))
                search_results[i] = {k: res[k] for k in ['title', 'type', 's3_Key', 'url', 'audio_url', 'pageNo'] if k in res.keys()}
            references = {"references": search_results}
        logger.info(f"Successfully processed: {llama_response[:50]}...")
        handler_end = time.time()
        handler_duration = handler_end - handler_start
        logger.info(f"Time Taken: {handler_duration:.3f} secs")
        cost = handler_duration * 1
        # TODO: Cost yet need to add here
        return {'KNOWLEDGEBASE.STATUS': "Completed",
                "KNOWLEDGEBASE.ID ": str(kbId),
                "KNOWLEDGEBASE.CONTENT": {'llama_response': llama_response, "total_tokens": total_tokens, "cost": cost,
                                          **references},
                "KNOWLEDGEBASE.CONTENT_TYPE": "query"}

    except Exception as e:
        print(e)
        return {'KNOWLEDGEBASE.STATUS': "Failed", 'body': json.dumps({'error': f'{e}'})}


runpod.serverless.start({
    "handler": runpod_handler
})
