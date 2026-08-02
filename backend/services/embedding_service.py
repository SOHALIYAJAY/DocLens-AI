# services/embedding_service.py
from sentence_transformers import SentenceTransformer
from typing import List
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

# We load a small, fast local model for creating embeddings.
# "all-MiniLM-L6-v2" is standard and efficient for sentence/paragraph embeddings.
MODEL_NAME = "all-MiniLM-L6-v2"
model = SentenceTransformer(MODEL_NAME)

def generate_embeddings(texts: List[str]) -> List[list]:
    """
    Generate dense vector embeddings for a list of text chunks.
    
    Args:
        texts (List[str]): A list of string chunks.
        
    Returns:
        List[list]: A list of vectors (as Python lists) corresponding to each chunk.
    """
    if not texts:
        return []
    
    # model.encode returns a numpy array, we convert it to a list
    embeddings = model.encode(texts, convert_to_numpy=True).tolist()
    return embeddings
    
class MiniLMEmbeddingFunction(EmbeddingFunction):
    """
    Wrapper for ChromaDB to use our loaded SentenceTransformer model.
    """
    def __call__(self, input: Documents) -> Embeddings:
        return generate_embeddings(input)
    
def get_embedding_dimension() -> int:
    """
    Returns the dimension of the embeddings produced by this model.
    """
    return model.get_sentence_embedding_dimension()
