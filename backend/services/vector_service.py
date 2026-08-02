# services/vector_service.py
import chromadb
from typing import List, Dict, Any
from services.embedding_service import MiniLMEmbeddingFunction
import os

# Ensure the database is saved in a specific backend directory
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".chroma_db")
client = chromadb.PersistentClient(path=DB_PATH)
embedding_function = MiniLMEmbeddingFunction()
COLLECTION_NAME = "pdf_knowledge_base"

def _get_collection():
    """Gets or creates the active Chroma collection."""
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function
    )

def clear_knowledge_base():
    """
    Clears the current knowledge base (used before uploading a new PDF for single-doc QA).
    """
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

def add_to_knowledge_base(chunks: List[Dict[str, Any]]):
    """
    Adds chunks (with page metadata) to the global knowledge base.
    
    Args:
        chunks (List[Dict]): The text chunks with 'page' and 'text'.
    """
    if not chunks:
        return
        
    collection = _get_collection()
    
    documents = [c["text"] for c in chunks]
    metadatas = [{"page": c.get("page", 1)} for c in chunks]
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

def search_knowledge_base(query: str, top_k: int = 8) -> List[Dict[str, Any]]:
    """
    Searches ChromaDB for the top_k most similar chunks.
    
    Args:
        query (str): The string query.
        top_k (int): Number of results to return.
        
    Returns:
        List[Dict]: The top_k most relevant text chunks with metadata.
    """
    collection = _get_collection()
    
    # query_texts automatically creates embeddings using the embedding_function
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    
    retrieved = []
    if results['documents'] and len(results['documents'][0]) > 0:
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        distances = results['distances'][0]
        
        for doc, meta, dist in zip(docs, metas, distances):
            # Optional: Add a distance threshold check here if desired
            retrieved.append({
                "text": doc,
                "page": meta.get("page", 1) if meta else 1,
                "distance": dist
            })
            
    return retrieved

def get_all_chunks() -> List[str]:
    """
    Returns all text chunks currently in the knowledge base (as plain strings).
    """
    try:
        collection = _get_collection()
        results = collection.get()
        return results.get("documents", [])
    except Exception:
        return []
