from .runpod_pipeline import runpod_llama_pipeline


def generate_response(user_query, text, conversation, temperature, top_k, top_p, max_tokens, frequency_penalty,
                      presence_penalty, stop):
    """

    :param user_query:
    :param text:
    :param conversation:
    :param temperature:
    :param top_k:
    :param top_p:
    :param max_tokens:
    :param frequency_penalty:
    :param presence_penalty:
    :param stop:
    :return:
    """

    msg = [
        {'role': 'system', 'content': 'You are Woice chatbot who always responds to user queries'},
        {'role': 'user', 'content': 'Give a response with helpful tone and avoid unnecessary details'}
    ]

    # Adding the conversation history
    con = {'role': 'user', 'content': f'This is past conversation: {conversation}'}
    msg.append(con)

    # Adding the user query
    user_query_msg = {'role': 'user', 'content': f'Answer user query.The user query is: {user_query}'}
    msg.append(user_query_msg)

    # print("msg",msg)

    # Adding the KB data for the LLM to use
    text_data_msg = {'role': 'user',
                     'content': f'Use the following text data only when user asks the relevant query to the following: '
                                f'{text}'}
    msg.append(text_data_msg)

    chat_completion_kwargs = {
        "temperature": temperature,
        "top_k": top_k,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "stop": stop
    }
    generated_text = runpod_llama_pipeline(text=msg, chat_completion_kwargs=chat_completion_kwargs)

    return generated_text
