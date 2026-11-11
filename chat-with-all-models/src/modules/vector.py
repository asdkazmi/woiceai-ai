from time import time
import logging
from bson.objectid import ObjectId

from .stella import TextProcessor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

retrieval = TextProcessor()


def vector_search(collection, query, kbId, custom_db, index='bgeVectors', path='bgeVectors', limit=3, threshold=0.5):
    t = time()
    unique_key_map = {
        "document-kb": "kbId",
    }

    unique_key = unique_key_map.get(collection.name)
    embedding = retrieval.stella_embedding_model.encode(query, prompt_name="s2p_query")

    pipeline = [{
        "$vectorSearch": {
            "index": index,
            "path": path,
            "queryVector": embedding.tolist(),
            "exact": True,
            "limit": limit
        }
    }, {
        '$project': {
            '_id': 0,
            'title': 1,
            unique_key: 1,
            'content': 1,
            'metadata': 1,
            'type': 1,
            's3_Key': 1,
            'url': 1,
            'audio_url': 1,
            'reference_to_user_db': 1,
            "score": {"$meta": "vectorSearchScore"}
        }
    }]

    if kbId:
        pipeline[0]["$vectorSearch"]['filter'] = {unique_key: str(kbId)}

    t = time()
    results = collection.aggregate(pipeline)
    logger.info(f'MongoDB vector search time: {(time() - t):.3f} sec')

    results_list = []
    for res in results:
        results_list.append(res)
        if res['score'] < threshold:
            break

        # Process each element in results_list
    if custom_db is not None:
        for res in results_list:
            if 'reference_to_user_db' in res and isinstance(res['reference_to_user_db'], ObjectId):
                ref_id = res['reference_to_user_db']
                # Fetch the document content from the database
                document = custom_db['document-kb'].find_one({"_id": ref_id}, {"_id": 0, "content": 1})
                if document:
                    # Add the content to the current element
                    res['content'] = document["content"]
                else:
                    logger.warning(f"No document found for ObjectId {ref_id}")
            else:
                logger.debug(f"No valid reference_to_user_db for result: {res}")


    return results_list
