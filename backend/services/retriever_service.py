# services/retriever_service.py
from typing import List
from services.hybrid_retriever_service import retrieve_hybrid_chunks
from services.reranker_service import reranker_service
from services.context_expansion_service import context_expansion_service
from core.config import settings

def retrieve_relevant_chunks(query: str, top_k: int = None, max_distance: float = 1.5) -> List[str]:
    """
    Retrieves the most relevant text chunks using Hybrid Search (Vector + BM25 RRF),
    Cross-Encoder Reranking, and Parent/Neighbor Context Expansion.
    
    Args:
        query (str): The user's question.
        top_k (int, optional): Target number of top reranked chunks to return.
        
    Returns:
        List[str]: Formatted context blocks with complete section and page metadata.
    """
    if not query:
        return []
        
    # 1. Hybrid Retrieval (ChromaDB Vector + BM25 RRF -> 15 candidates)
    hybrid_candidates = retrieve_hybrid_chunks(query)
    
    # 2. Cross-Encoder Reranking (15 candidates -> top 5 reranked candidates)
    target_k = top_k or settings.RERANK_TOP_K
    reranked_results = reranker_service.rerank(query, hybrid_candidates, top_k=target_k)
    
    # 3. Context Expansion (Parent section + contiguous neighbor chunks)
    expanded_blocks = context_expansion_service.expand_chunks(query, reranked_results)
    
    formatted_chunks = []
    
    for res in expanded_blocks:
        page_start = res.get("page_start", res.get("page_number", 1))
        page_end = res.get("page_end", res.get("page_number", 1))
        page_str = f"Page {page_start}" if page_start == page_end else f"Pages {page_start}-{page_end}"

        section = res.get("section") or res.get("metadata", {}).get("section", "")
        heading = res.get("heading") or res.get("metadata", {}).get("heading", "")
        content_type = res.get("content_type") or res.get("metadata", {}).get("content_type", "text")
        text = res.get("text", "")

        header_parts = [f"[{page_str}]"]
        if section and section != "General":
            header_parts.append(f"[Section: {section}]")
        if heading and heading != section:
            header_parts.append(f"[Heading: {heading}]")
        if content_type and content_type != "text":
            header_parts.append(f"[{content_type.upper()}]")

def retrieve_relevant_chunks_with_metadata(query: str, top_k: int = None, max_distance: float = 1.5) -> tuple[List[str], List[dict]]:
    """
    Retrieves relevant text chunks and raw metadata dictionaries.
    """
    if not query:
        return [], []
        
    hybrid_candidates = retrieve_hybrid_chunks(query)
    target_k = top_k or settings.RERANK_TOP_K
    reranked_results = reranker_service.rerank(query, hybrid_candidates, top_k=target_k)
    expanded_blocks = context_expansion_service.expand_chunks(query, reranked_results)
    
    formatted_chunks = []
    metadata_list = []
    
    for res in expanded_blocks:
        page_start = res.get("page_start", res.get("page_number", 1))
        page_end = res.get("page_end", res.get("page_number", 1))
        page_str = f"Page {page_start}" if page_start == page_end else f"Pages {page_start}-{page_end}"

        section = res.get("section") or res.get("metadata", {}).get("section", "")
        heading = res.get("heading") or res.get("metadata", {}).get("heading", "")
        content_type = res.get("content_type") or res.get("metadata", {}).get("content_type", "text")
        table_id = res.get("table_id") or res.get("metadata", {}).get("table_id", "")
        figure_id = res.get("figure_id") or res.get("metadata", {}).get("figure_id", "")
        text = res.get("text", "")

        header_parts = [f"[{page_str}]"]
        if section and section != "General":
            header_parts.append(f"[Section: {section}]")
        if heading and heading != section:
            header_parts.append(f"[Heading: {heading}]")
        if content_type and content_type != "text":
            header_parts.append(f"[{content_type.upper()}]")

        header_str = " ".join(header_parts)
        formatted_chunks.append(f"{header_str}\n{text}")
        
        metadata_list.append({
            "page_number": int(page_start),
            "page_start": int(page_start),
            "page_end": int(page_end),
            "section": section,
            "heading": heading,
            "content_type": content_type,
            "table_id": table_id,
            "figure_id": figure_id
        })
            
    unique_chunks = list(dict.fromkeys(formatted_chunks))
    return unique_chunks, metadata_list



