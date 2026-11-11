import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def rewrite_query(query, chat_history, llm, restricted_questions):
    restricted_questions_list = ""
    validation_messages_list = ""
    system_prompt = ""
    user_message = ""
    validation_messages = []
    if restricted_questions:
        restricted_questions_list = "\n  ".join(
            [f"{i + 1}. {question}" for i, question in enumerate(restricted_questions)])
        with open('messages.json', 'r') as file:
            data = json.load(file)
        validation_messages = data.get("private-validation-messages", [])
        validation_messages_list = "\n  ".join([f"{i + 1}. {answer}" for i, answer in enumerate(validation_messages)])

    if chat_history:
        system_prompt = (f"You are an intelligent assistant. Rewrite the given query by replacing any pronoun with its corresponding"
                         f" noun based on the previous queries provided in the chat history. Do not modify any other part of the query. Strictly do "
                         f"not add any word in the question from your own. just replace existing unknown pronouns with their corresponding nouns."
                         f"If there are no unknown pronouns in the query then return the query as it is."
                         f" For example, 'when it was founded' and here 'it' is unknown and relevant "
                         f"word for this in chat history is microsoft so that can be filled from chat history like 'when "
                         f"microsoft was founded'. You just have to update the query and strictly do not give answer of "
                         f"the query")
    if restricted_questions:
        system_prompt += (
            "\n\nYou have given a list of restricted queries and if user query is from these restricted queries then strictly you have not to answer user query."
            "\n\nIf there is no chat history and neither query is from restricted queries then you strictly have to return query as it is")
    message = [{'role': 'system', 'content': system_prompt}]
    if chat_history:
        length = len(chat_history)
        chat_mes = '\n'.join(
            [f"{'user' if _['is_human'] else 'assistant'}: {_['prompt']}" for _ in chat_history[-min(length, 6):]])
        one_shot_example1 = [
            {"role": "user", "content": '''Here is the chat history,just use this for above query: 
                                                user: What is Rev9 Solutions
                                                assistant: Rev9 Solutions is a Pakistani organization that is providing the services of software developments.
                                                and you have to update this Query: when it was founded'''},
            {"role": "assistant", "content": "when Rev9 Solutions was founded"}]
        one_shot_example2 = [
            {"role": "user", "content": '''Here is the chat history,just use this for above query: 
                                                user: heloo i am mehjabeen kazmi student of computer science. 
                                                assistant: Hello Mehjabeen Kazmi! How are you today?
                                                and you have to update this Query: what jobs i have to look for?'''},
            {"role": "assistant", "content": "what jobs Mehjabeen Kazmi have to look for?"}]
        message.extend(one_shot_example1)
        message.extend(one_shot_example2)
        user_message += (f"Here is the chat history,just use this for above query: \n{chat_mes} \nand you have "
                         f"to update this Query: {query}")
    if restricted_questions:
        user_message = f"\n\nIf query is related to one of the following restricted queries as: \n  {restricted_questions_list}  \nThen you strictly have to give answer from one of these: \n  {validation_messages_list}"
        user_message += f"\nIf query is not from restricted query and there is no chat history then return query as it is as: \n{query}"
    message.append({'role': 'user',
                    'content': user_message})
    response = llm.create_chat_completion(
        messages=message  # Pass keyword arguments specific to create_chat_completion
    )
    return response['choices'][0]['message']['content'], response['usage'].get("total_tokens"), validation_messages
