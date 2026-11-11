from .llama_gemfilter.load_model import load_model
from .llama_gemfilter.my_generation import set_topk, my_greedy_generate_selection, my_greedy_generate_standard
import torch
import re


def gemfilter(messages, model, tokenizer):
    select_layer_idx = 13
    # inputs = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    # inputs = inputs.replace("\n\nCutting Knowledge Date: December 2023\nToday Date: 26 Jul 2024", "")

    # Check how the model performs
    prompt = tokenizer(messages, return_tensors="pt")
    input_ids = prompt['input_ids'].to("cuda")
    attn_mask = prompt["attention_mask"].to("cuda")

    print("After tokenization, there is %d tokens" % len(input_ids[0]))

    with torch.no_grad():
        response = my_greedy_generate_selection(
            input_ids, attn_mask, model, tokenizer, max_gen_len=200, select_layer_idx=select_layer_idx,
            print_context=False)
    content = re.search(r'<book>(.*?)</book>', response, re.DOTALL)
    content = content.group(1)


    return content
