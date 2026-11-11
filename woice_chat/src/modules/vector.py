from time import time
from .runpod_pipeline import runpod_api_pipeline
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def vector_search(collection, userId, index='bgeVectors', path='bgeVectors', num_candidates=10, limit=3,
                  query_vector=[],
                  query="", reference_ids=[]):
    """
    The code defines an aggregation pipeline that performs a vector search on a MongoDB collection. The pipeline filters
    documents based on a query vector, projects specific fields, and sorts the results by score. The code also adds a
    filter clause to the vector search stage to filter results by a list of reference IDs.
    :param collection:
    :param userId:
    :param index:
    :param path:
    :param num_candidates:
    :param limit:
    :param query_vector:
    :param query:
    :param reference_ids:
    :return:
    """
    t = time()
    unique_key_map = {
        "chunks": "docId",

    }

    unique_key = unique_key_map.get(collection.name)

    if query:
        logger.info(f"Calling runpod API for generating query embeddings")
        query_vector = runpod_api_pipeline(substrings=[query], task='embeddings')
        # query_vector = ss._get_query_embedding(query=[query]).tolist()

    logger.info(f'Query embedding time: {(time() - t):.3f} sec')

    pipeline = [{
        "$vectorSearch": {
            "index": index,
            "path": path,
            "queryVector": query_vector[0],
            "numCandidates": num_candidates,
            "limit": limit
        }
    }, {
        '$project': {
            '_id': 0,
            'title': 1,
            unique_key: 1,
            'content': 1,
            'metadata': 1,
            "score": {"$meta": "vectorSearchScore"}
        }
    }]

    if reference_ids:
        pipeline[0]["$vectorSearch"]['filter'] = {unique_key: {"$in": reference_ids}}

    t = time()
    results = collection.aggregate(pipeline)
    logger.info(f'MongoDB vector search time: {(time() - t):.3f} sec')

    results_list = []
    for res in results:
        results_list.append(res)

    return results_list
