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
    Adds chunks (with full metadata) to the global knowledge base in ChromaDB.
    
    Args:
        chunks (List[Dict]): The text chunks containing metadata and text.
    """
    if not chunks:
        return
        
    collection = _get_collection()
    
    documents = []
    metadatas = []
    ids = []
    
    for i, c in enumerate(chunks):
        doc_text = c.get("text", "")
        if not doc_text:
            continue
            
        chunk_id = c.get("chunk_id", f"chunk_{i}")
        
        # Build metadata dictionary with primitive values only
        meta = {
            "document_id": str(c.get("document_id", "doc_default")),
            "document_name": str(c.get("document_name", "document.pdf")),
            "page_number": int(c.get("page_number", c.get("page", 1))),
            "page_start": int(c.get("page_start", c.get("page", 1))),
            "page_end": int(c.get("page_end", c.get("page", 1))),
            "section": str(c.get("section", "")),
            "heading": str(c.get("heading", "")),
            "chapter": str(c.get("chapter", "")),
            "subsection": str(c.get("subsection", "")),
            "parent_section": str(c.get("parent_section", "")),
            "chunk_id": str(chunk_id),
            "parent_chunk_id": str(c.get("parent_chunk_id", "")),
            "content_type": str(c.get("content_type", "text")),

            "figure_id": str(c.get("figure_id", "")),
            "table_id": str(c.get("table_id", "")),
            "caption": str(c.get("caption", "")),
            "source_type": str(c.get("source_type", "pdf")),
            "page": int(c.get("page", c.get("page_number", 1)))
        }
        
        documents.append(doc_text)
        metadatas.append(meta)
        ids.append(chunk_id)
        
    if documents:
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[CHROMADB] Indexed {len(documents)} chunks into collection '{COLLECTION_NAME}'")

def search_knowledge_base(query: str, top_k: int = 8) -> List[Dict[str, Any]]:
    """
    Searches ChromaDB for the top_k most similar chunks.
    
    Args:
        query (str): The string query.
        top_k (int): Number of results to return.
        
    Returns:
        List[Dict]: The top_k most relevant text chunks with metadata dict included.
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
        ids = results['ids'][0] if 'ids' in results and results['ids'] else [None]*len(docs)
        
        for doc, meta, dist, cid in zip(docs, metas, distances, ids):
            meta_dict = meta if isinstance(meta, dict) else {}
            retrieved_item = {
                "text": doc,
                "page": meta_dict.get("page_number", meta_dict.get("page", 1)),
                "page_number": meta_dict.get("page_number", meta_dict.get("page", 1)),
                "page_start": meta_dict.get("page_start", 1),
                "page_end": meta_dict.get("page_end", 1),
                "section": meta_dict.get("section", ""),
                "heading": meta_dict.get("heading", ""),
                "chunk_id": meta_dict.get("chunk_id", cid or ""),
                "content_type": meta_dict.get("content_type", "text"),
                "distance": dist,
                "metadata": meta_dict
            }
            retrieved.append(retrieved_item)
            
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

