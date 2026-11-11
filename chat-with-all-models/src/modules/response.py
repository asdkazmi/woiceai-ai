from .llama import generate as llama
from .applygemfilter import gemfilter
from .generate_prompt import generate_prompt
import re


def generate_response(user_query, contents, metadata_list, history, external_knowledge_access, llm, enable_reference, model, tokenizer,
                      user_system_prompt="", **kwargs):
    """

    :param enable_reference:
    :param llm:
    :param external_knowledge_access:
    :param user_query:
    :param knowledge:
    :param history:
    :param user_system_prompt:
    :return:
    """
    prompt = "\n<|im_start|> This is a very long story book: <book> %s </book>.\n" % contents
    prompt += "Based on the content of the book, Question: %s\nAnswer:" % user_query
    content = gemfilter(prompt, model, tokenizer)

    sep = '-' * 20
    content_sections = content.split(sep)

    knowledge = []
    for i, (content, metadata) in enumerate(zip(content_sections, metadata_list)):
        chunk = f'METADATA: {{ "index": {i + 1}, {metadata} }} \n{content.strip()}'
        knowledge.append(chunk)

    sep = '-' * 20
    knowledge = f'\n{sep}\n\n'.join(knowledge)
    msgs, user_query= generate_prompt(external_knowledge_access, enable_reference, user_system_prompt, knowledge, user_query)
    if len(history):
        updated_history = [history[0]]
        for msg in history[1:]:
            if msg['is_human'] == updated_history[-1]['is_human']:
                updated_history[-1]['prompt'] += f"\n{msg['prompt']}"
            else:
                updated_history.append(msg)

        for msg in updated_history:
            msgs.append({'role': 'user' if msg['is_human'] else 'assistant', 'content': msg['prompt']})

    msgs.append({'role': 'user', 'content': user_query})
    generated_text, total_tokens = llama(messages=msgs, llm=llm, kwargs=kwargs)
    if enable_reference:
        generated_text = re.sub(r"\[index\]\([^()[\]]+\)", '', generated_text)

    return generated_text, total_tokens
