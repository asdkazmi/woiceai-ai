import logging

import numpy as np
import pandas as pd
import torch

device = 'cuda' if torch.cuda.is_available() else 'cpu'

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class SemanticSearch:
    def __init__(self, model, tokenizer):
        self.tokenizer = tokenizer
        self.model = model.to(device)

    def process_text(self, query, substrings, top_k=5):
        query_embedding = self._get_query_embedding(query)
        all_embeddings_array = self._get_substrings_embeddings(substrings)
        top_indices = self._calculate_similarity(query_embedding, all_embeddings_array, top_k)
        new_data_list = self._get_top_similar_texts(substrings, top_indices)
        self._log_processed_query(query)
        return new_data_list

    def _get_substrings_embeddings(self, substrings):
        all_embeddings = []
        for substr in substrings:
            embeddings = self._get_query_embedding(substr)
            all_embeddings.append(embeddings)
        all_embeddings_array = np.vstack(all_embeddings)
        return all_embeddings_array

    def _get_query_embedding(self, query):
        inputs = self.tokenizer(query, padding=True, truncation=True, return_tensors='pt', max_length=256,
                                add_special_tokens=True, return_attention_mask=True, return_token_type_ids=False)
        with torch.no_grad():
            outputs = self.model(**inputs.to(device))

        attention_mask = inputs['attention_mask']

        last_hidden = outputs.last_hidden_state.masked_fill(~attention_mask[..., None].bool(), 0.0)
        embeddings = last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]
        return embeddings.cpu().numpy()

    def _calculate_similarity(self, query_embedding, all_embeddings_array, top_k):
        all_embeddings_flat = all_embeddings_array.reshape(all_embeddings_array.shape[0], -1)
        scores = np.dot(all_embeddings_flat, query_embedding.T).squeeze()
        scores_dict = dict(zip(np.arange(0, len(scores)), scores.tolist()))
        return pd.Series(scores_dict).sort_values(ascending=False).index.to_list()[:top_k]

    def _get_top_similar_texts(self, substrings, top_indices):
        return [substrings[i] for i in top_indices]

    def _log_processed_query(self, query):
        logger.info(f"Processed query '{query}' with substrings and obtained similar texts.")
