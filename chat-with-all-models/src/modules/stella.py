import copy
from sentence_transformers import SentenceTransformer
import time
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# TODO: Replace Setence Transformer based Llama with GGUF version of Stella 1.5B model located here: https://huggingface.co/abhishekbhakat/stella_en_1.5B_v5_GGUF
stella_embedding_model = SentenceTransformer("stella_en_400M_v5", trust_remote_code=True, device="cuda")


class TextProcessor:
    def __init__(self):
        """
        Initializes the TextProcessor with a stella_embedding_model for encoding vectors.

        Parameters:
        stella_embedding_model: The embedding model used to encode text.
        """
        self.stella_embedding_model = stella_embedding_model

    def create_chunk(self, content, chunk_size=100, overlap=20):
        """
        Splits the given content into chunks of specified size with overlap.

        Parameters:
        content (str): The input text to be chunked.
        chunk_size (int): The size of each chunk.
        overlap (int): The overlap size between consecutive chunks.

        Returns:
        list: A list of text chunks.
        """
        if not content:
            return []

        # Convert the content to a list of words
        words = content.split()

        # Prepare chunks
        chunks = []
        start = 0
        while start < len(words):
            # Get the chunk
            chunk = words[start:start + chunk_size]
            chunks.append(" ".join(chunk))

            # Move start by chunk_size - overlap
            start += chunk_size - overlap

        return chunks

    def camel_to_text(self, text):
        """
        Converts a camelCase or mixed-case string into a formatted string with spaces and capitalized words.

        Parameters:
        text (str): The input string in camelCase or mixed-case format.

        Returns:
        str: A formatted string with spaces and capitalized words.
        """
        if not text:
            return ""

        formatted = ''.join([' ' + char if char.isupper() else char for char in text]).strip()

        # Capitalize each word
        return formatted.title()

    def stella_vectors(self, documents):
        """
        Encodes documents with metadata and content using the Stella embedding model.

        Parameters:
        documents (list): List of documents where each document is a dictionary with 'content' and metadata.

        Returns:
        list: A list of encoded vectors for each document.
        """
        documents_copy = copy.deepcopy(documents)
        all_contents = []
        for doc in documents_copy:
            content = doc.pop('content')
            metadata = "; ".join([f"{self.camel_to_text(key)}: {value}" for key, value in doc.items()])
            content = metadata + "\n\n" + content
            all_contents.append(content)

        vectors = self.stella_embedding_model.encode(all_contents)
        return vectors

    def process_documents(self, inputs, chunk_size=100, overlap=20):
        """
        Processes the documents by chunking the content, adding metadata, and generating embeddings.

        Parameters:
        inputs (list): List of input documents, where each document is a dictionary.
        chunk_size (int): The size of each chunk for text splitting.
        overlap (int): The overlap size for chunks.

        Returns:
        list: List of documents with 'stellaVectors' embedded for each chunk.
        """
        output = []
        for inp in inputs:
            content = inp.pop('content')
            chunks = self.create_chunk(content, chunk_size=chunk_size, overlap=overlap)
            for chunk in chunks:
                doc = {'pageNo': 1, 'content': chunk, **inp}
                output.append(doc)

        all_vectors = self.stella_vectors(output)
        for i in range(len(output)):
            output[i]['stellaVectors'] = all_vectors[i]

        return output

    def get_docs_embeddings(self, documents, chunk_size=100, overlap=20):
        output = []
        for inp in documents:
            chunks = self.create_chunk(inp, chunk_size=chunk_size, overlap=overlap)
            output.extend(chunks)

        all_vectors = self.stella_embedding_model.encode(output)

        return all_vectors

    def __call__(self, inputs):

        text = inputs['text']
        queries = inputs.get('queries')
        top_k = inputs.get('top_k', 10)
        task = inputs.get('task', 'retrieval')

        st = time.time()
        if task == 'embeddings':
            embeddings = self.stella_embedding_model.encode(text)
            logger.info(f"Embeddings generation time: {(time.time() - st):.3f} sec")
            return {"output": embeddings.tolist()}

        elif task == 'retrieval':

            text_embeddings = self.get_docs_embeddings(documents=text, chunk_size=350, overlap=50)
            query_embedding = self.stella_embedding_model.encode(queries, prompt_name="s2p_query")
            similarities = self.stella_embedding_model.similarity(query_embedding, text_embeddings)
            all_retrievals = list()

            for sim in similarities:
                sorted_similarities = [x for _, x in reversed(sorted(zip(sim, text)))][:top_k]
                all_retrievals.append(sorted_similarities)
            if type(queries) == str:
                all_retrievals = all_retrievals[0]
            logger.info(f"Relative information retrieval time: {(time.time() - st):.3f} sec")
            return {"output": all_retrievals}
