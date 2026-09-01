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


def chunk_text_by_tokens(
    text: str, 
    max_tokens_per_chunk: int = 6500, 
    overlap_tokens: int = 400
) -> List[str]:
    """
    Splits document text into chunks targeting ~6,000-7,000 tokens per chunk
    with ~300-500 tokens of overlap, preserving paragraph/sentence boundaries
    and original document sequence.
    
    Args:
        text (str): The full PDF text to be chunked.
        max_tokens_per_chunk (int): Maximum target tokens per chunk (default 6500).
        overlap_tokens (int): Token overlap between consecutive chunks (default 400).
        
    Returns:
        List[str]: List of text chunks preserving document order.
    """
    if not text or not text.strip():
        return []
        
    from services.token_service import count_tokens

    # Small text optimization: return single chunk if within limit
    if count_tokens(text) <= max_tokens_per_chunk:
        return [text]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_tokens_per_chunk,
        chunk_overlap=overlap_tokens,
        length_function=count_tokens,
        separators=[
            "\n\n# ", "\n\n## ", "\n\n### ",
            "\n\n1. ", "\n\n2. ", "\n\n3. ", "\n\n4. ", "\n\n5. ", "\n\n6. ", "\n\n7. ", "\n\n8. ",
            "\n\nABSTRACT", "\n\nINTRODUCTION", "\n\nMETHODOLOGY", "\n\nMETHODS", "\n\nRESULTS", "\n\nDISCUSSION", "\n\nCONCLUSION", "\n\nLIMITATIONS",
            "\n\n",
            "\n",
            ". ", "? ", "! ",
            " ", ""
        ],
        is_separator_regex=False,
    )

    return splitter.split_text(text)

