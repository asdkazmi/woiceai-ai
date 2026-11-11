import json
import time
import logging

logger = logging.getLogger(__name__)
from modules.credits import cost
from modules.vector import vector_search
from modules.mongo import db
from modules.response import generate_response


def lambda_handler(event, context):
    handler_start = time.time()
    req_data = json.loads(event.get("body", json.dumps(event)).strip())
    user_query = req_data.get('user_query', None)
    kbId = req_data.get('kbId', None)
    history = req_data.get('history', None)
    prompts = [item['prompt'] for item in history] if history else []
    chat_arg = req_data.get('chat_arg', {})
    temperature = chat_arg.get('temperature', 0.2)
    top_k = chat_arg.get('top_k', 40)
    top_p = chat_arg.get('top_p', 0.95)
    max_tokens = chat_arg.get('max_tokens', None)
    frequency_penalty = chat_arg.get('frequency_penalty', 0.0)
    presence_penalty = chat_arg.get('presence_penalty', 0.0)
    stop = chat_arg.get('stop', [])

    """
      "history": [
    {is_human: true, prompt: "How are you doing?"},
    {is_human: false, prompt: "Hi! I'm good, how are you?"}
    """

    logger.info("Api called!!!")
    # call sns for processing here and return status : "processing"

    if not kbId:
        return {'KNOWLEDGEBASE.STATUS': "Failed", 'body': json.dumps({'message': 'kbId is required'})}

    elif user_query and kbId:
        try:
            result, execution_time_embeddings = vector_search(collection=db["chunks"], kbId=kbId, query=user_query)
            res = ''
            for i in range(len(result)):
                res += result[i].get("content")

            print("Generating Response..")

            if history:
                llama_response, execution_time_llama = generate_response(user_query=user_query, text=res,
                                                                         conversation=prompts,
                                                                         temperature=temperature, top_k=top_k,
                                                                         top_p=top_p,
                                                                         max_tokens=max_tokens,
                                                                         frequency_penalty=frequency_penalty,
                                                                         presence_penalty=presence_penalty,
                                                                         stop=stop)

            else:
                llama_response, execution_time_llama = generate_response(user_query=user_query, text=res,
                                                                         conversation=None,
                                                                         temperature=temperature, top_k=top_k,
                                                                         top_p=top_p,
                                                                         max_tokens=max_tokens,
                                                                         frequency_penalty=frequency_penalty,
                                                                         presence_penalty=presence_penalty,
                                                                         stop=stop)
            print(f"Successfully processed: {llama_response}")
            handler_end = time.time()
            handler_duration = handler_end - handler_start
            credits_consumed = cost(handler_duration, execution_time_embeddings, execution_time_llama)
            return {'KNOWLEDGEBASE.STATUS': "Completed",
                    "KNOWLEDGEBASE.ID ": kbId,
                    "KNOWLEDGEBASE.CONTENT": {'llama_response': llama_response, "credits_consumed": credits_consumed},
                    "KNOWLEDGEBASE.CONTENT_TYPE": "query"}

        except Exception as e:
            print(e)
            return {'KNOWLEDGEBASE.STATUS': "Failed", 'body': json.dumps({'error': f'{e}'})}
