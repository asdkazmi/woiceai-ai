import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def generate(messages, llm, kwargs={}):
    try:
        response = llm.create_chat_completion(
            messages=messages,
            **kwargs  # Pass keyword arguments specific to create_chat_completion
        )
        return response['choices'][0]['message']['content'], response['usage'].get("total_tokens")
    except Exception as e:
        logger.error(f"Error generating data: {e}")
        return None
