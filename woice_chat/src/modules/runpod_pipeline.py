import logging
import requests
import time
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def make_request(base_url, endpoint, payload=None, method="post"):
    """
    Makes a request to the Runpod API with the given base URL, endpoint, payload, and method.
    :param base_url:
    :param endpoint:
    :param payload:
    :param method:
    :return:
    """
    url = f"{base_url}/{endpoint}"
    # runpod_api_key = os.getenv("RUNPOD_API_KEY")
    runpod_api_key = os.getenv('RUNPOD_API_KEY')
    headers = {"Authorization": f"Bearer {runpod_api_key}"}
    if method == "post":
        response = requests.post(url, headers=headers, json=payload)
        return response.status_code, response.json()
    elif method == "get":
        response = requests.get(url, headers=headers)
        return response.status_code, response.json()


def wait_for_completion(base_url, queue_id, threshold):
    start_time = time.time()

    while time.time() - start_time < threshold:
        status_code, response = make_request(base_url, f"status/{queue_id}", method="get")

        if status_code == 200 and response.get('status') == 'COMPLETED':
            return response

        time.sleep(2)

    return None


def cancel_request(base_url, queue_id):
    logger.info("Threshold reached, cancelling request")

    cancel_code, cancel_response = make_request(base_url, f"cancel/{queue_id}", method="post")

    if cancel_code == 200:
        return {"status": "Request canceled"}
    else:
        return {"status": "Unable to cancel request"}


def runpod_api_pipeline(substrings, query='', top_k=5, threshold=30, task='embeddings'):
    """
    Runs a pipeline on the Runpod LLaMA API, sending a request and waiting for completion.
    :param substrings:
    :param query:
    :param top_k:
    :param threshold:
    :param task:
    :return:
    """
    # base_url = os.getenv("RUNPOD_BASE_URL")

    base_url = os.getenv('RUNPOD_BASE_URL')
    data_payload = {
        "input": {"text": substrings, "task": task}} if substrings is not None else {}

    method_a_response_code, method_a_response = make_request(base_url=base_url, endpoint="runsync",
                                                             payload=data_payload)

    if method_a_response_code == 200 and method_a_response.get("status") == 'COMPLETED':
        return method_a_response["output"]["output"]

    elif method_a_response.get("status") == "IN_PROGRESS" or method_a_response.get("status") == "IN_QUEUE":
        in_progress_id = method_a_response.get('id')
        logger.info("Q. ID: ", in_progress_id)
        result = wait_for_completion(base_url, in_progress_id, threshold)

        if result:
            return result["output"]["output"]

        return cancel_request(base_url, in_progress_id)

    else:
        logger.info("RUNSYNC API failed, attempting RUN API")
        method_b_response_code, method_b_response = make_request(base_url=base_url, endpoint="run",
                                                                 payload=data_payload)

        if method_b_response_code == 200:
            queue_id = method_b_response.get('id')
            result = wait_for_completion(base_url, queue_id, threshold)

            if result:
                return result["output"]["output"]

            return cancel_request(base_url, queue_id)

        else:
            logger.info("Both methods failed")
            return {"status": "Both methods failed"}


def runpod_llama_pipeline(text, llm_kwargs=None, chat_completion_kwargs=None, threshold=100):
    # base_url = os.getenv("RUNPOD_URL")
    base_url = os.getenv('BASE_URL_LLAMA')
    data_payload = {}
    if text is not None:
        data_payload["input"] = {"text": text}
        if llm_kwargs:
            data_payload["input"]["llm_kwargs"] = llm_kwargs
        if chat_completion_kwargs:
            data_payload["input"]["chat_completion_kwargs"] = chat_completion_kwargs

    method_a_response_code, method_a_response = make_request(base_url=base_url, endpoint="runsync",
                                                             payload=data_payload)

    if method_a_response_code == 200 and method_a_response.get("status") == 'COMPLETED':
        return method_a_response["output"]["output"]

    elif method_a_response.get("status") == "IN_PROGRESS" or method_a_response.get("status") == "IN_QUEUE":
        in_progress_id = method_a_response.get('id')
        print("Q. ID: ", in_progress_id)
        result = wait_for_completion(base_url, in_progress_id, threshold)

        if result:
            return result["output"]["output"]

        return cancel_request(base_url, in_progress_id)

    else:
        print("RUNSYNC API failed, attempting RUN API")
        method_b_response_code, method_b_response = make_request(base_url=base_url, endpoint="run",
                                                                 payload=data_payload)

        if method_b_response_code == 200:
            queue_id = method_b_response.get('id')
            result = wait_for_completion(base_url, queue_id, threshold)

            if result:
                return result["output"]["output"]

            return cancel_request(base_url, queue_id)

        else:
            print("Both methods failed")
            return {"status": "Both methods failed"}
