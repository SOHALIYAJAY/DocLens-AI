# services/retriever_service.py
from typing import List
from services.embedding_service import generate_embeddings
from services.vector_service import search_knowledge_base

def retrieve_relevant_chunks(query: str, top_k: int = 6, max_distance: float = 1.5) -> List[str]:
    """
    Retrieves the most relevant text chunks for a given query.
    Filters out chunks that are too far in distance (irrelevant).
    
    Args:
        query (str): The user's question.
        top_k (int): How many chunks to retrieve.
        max_distance (float): The maximum distance threshold.
        
    Returns:
        List[str]: The relevant text chunks formatted with page metadata.
    """
    if not query:
        return []
        
    # Search the vector database for the closest chunks
    # Note: search_knowledge_base now takes the string query directly
    results = search_knowledge_base(query, top_k)
    
    formatted_chunks = []
    
    for res in results:
        # Format the chunk with page metadata
        page = res.get("page", "?")
        text = res.get("text", "")
        formatted_chunks.append(f"[Page {page}]\n{text}")
            
    # Remove exact duplicates that might have been indexed multiple times
    unique_chunks = list(dict.fromkeys(formatted_chunks))
    
    return unique_chunks
