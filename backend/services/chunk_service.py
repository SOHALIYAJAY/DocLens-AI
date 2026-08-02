# services/chunk_service.py
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_text(pages: List[Dict[str, Any]], chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
    """
    Splits a list of page texts into smaller overlapping chunks using LangChain.
    Preserves page metadata for each chunk.
    
    Args:
        pages (List[Dict[str, Any]]): List of dicts with 'page' and 'text'.
        chunk_size (int): The maximum number of characters per chunk.
        overlap (int): The number of overlapping characters between chunks.
        
    Returns:
        List[Dict[str, Any]]: A list of text chunks with page metadata.
    """
    if not pages:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        is_separator_regex=False,
    )

    chunks = []
    
    for page_data in pages:
        page_num = page_data.get("page", 1)
        text = page_data.get("text", "")
        
        if not text.strip():
            continue
            
        page_chunks = text_splitter.split_text(text)
        
        for c in page_chunks:
            chunks.append({
                "page": page_num,
                "text": c
            })

    return chunks
