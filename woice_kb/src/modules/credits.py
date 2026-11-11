import json
import math
import os


def cost(handler_duration, execution_time_embeddings, execution_time_transcriber=None):
    try:
        embeddings_cost_per_second = float(os.getenv('RUNPOD_API_COST_PER_SECOND'))
        transcriber_cost_per_second = float(os.getenv('RUNPOD_TRANSCRIBER_COST_PER_SECOND'))
        cost_per_3gb_millisecond = float(os.getenv('COST_PER_3GB_MILLISECOND'))
        lambda_cost_per_3_gb_second = cost_per_3gb_millisecond * 1000  # Per 3 GB-second cost

        if execution_time_transcriber is None:
            embeddings_cost = embeddings_cost_per_second * execution_time_embeddings
            prompt_builder_cost = handler_duration * lambda_cost_per_3_gb_second
            total_credits_cents = math.ceil((embeddings_cost + prompt_builder_cost) * 1000)
        else:
            embeddings_cost = embeddings_cost_per_second * execution_time_embeddings
            transcriber_cost = transcriber_cost_per_second * execution_time_transcriber
            prompt_builder_cost = handler_duration * lambda_cost_per_3_gb_second
            total_credits_cents = math.ceil((embeddings_cost + transcriber_cost + prompt_builder_cost) * 1000)

        return total_credits_cents

    except Exception as e:
        print(e)
        return {'statusCode': 500, 'message': json.dumps({'error': f'{e}'})}


"""
Lambda woice kb
memory 1024	$0.0000000167/ms 
memory 3072	$0.0000000500/ms 

BGE 0.00019/s

Transcriber 0.00031/s

llama 0.00031/s
"""
