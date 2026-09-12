# services/hybrid_retriever_service.py
from typing import List, Dict, Any
from core.config import settings
from services.vector_service import search_knowledge_base
from services.bm25_service import bm25_service

def reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = 60,
    top_k: int = 15
) -> List[Dict[str, Any]]:
    """
    Combines vector search and BM25 lexical search results using Reciprocal Rank Fusion (RRF).
    
    RRF Score = 1 / (k + rank_vector) + 1 / (k + rank_bm25)
    
    Deduplicates candidates by chunk_id and returns structured result objects.
    """
    rrf_scores = {}
    chunk_data_map = {}
    sources_map = {}

    # 1. Process Vector Search Candidates
    for rank, item in enumerate(vector_results, start=1):
        cid = item.get("chunk_id") or item.get("metadata", {}).get("chunk_id")
        if not cid:
            text_snippet = item.get("text", "")[:50]
            cid = f"vec_{item.get('page', 1)}_{hash(text_snippet)}"

        score = 1.0 / (k + rank)
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score
        sources_map.setdefault(cid, []).append("vector")

        if cid not in chunk_data_map:
            chunk_data_map[cid] = dict(item)

    # 2. Process BM25 Search Candidates
    for rank, item in enumerate(bm25_results, start=1):
        cid = item.get("chunk_id") or item.get("metadata", {}).get("chunk_id")
        if not cid:
            text_snippet = item.get("text", "")[:50]
            cid = f"bm25_{item.get('page', 1)}_{hash(text_snippet)}"

        score = 1.0 / (k + rank)
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score
        if "bm25" not in sources_map.setdefault(cid, []):
            sources_map[cid].append("bm25")

        if cid not in chunk_data_map:
            chunk_data_map[cid] = dict(item)

    # 3. Sort candidates by final RRF score descending
    sorted_cids = sorted(rrf_scores.keys(), key=lambda c: rrf_scores[c], reverse=True)

    fused_results = []
    for cid in sorted_cids[:top_k]:
        item = chunk_data_map[cid]
        page_num = item.get("page_number") or item.get("page", 1)
        sec = item.get("section") or item.get("metadata", {}).get("section", "General")
        head = item.get("heading") or item.get("metadata", {}).get("heading", "")
        ctype = item.get("content_type") or item.get("metadata", {}).get("content_type", "text")
        
        structured_item = {
            "chunk_id": cid,
            "text": item.get("text", ""),
            "score": round(rrf_scores[cid], 6),
            "page_number": int(page_num),
            "page_start": int(item.get("page_start", page_num)),
            "page_end": int(item.get("page_end", page_num)),
            "section": sec,
            "heading": head,
            "content_type": ctype,
            "retrieval_sources": sources_map.get(cid, []),
            "metadata": item.get("metadata", {})
        }
        fused_results.append(structured_item)

    return fused_results

def retrieve_hybrid_chunks(
    query: str,
    vector_top_k: int = None,
    bm25_top_k: int = None,
    hybrid_top_k: int = None
) -> List[Dict[str, Any]]:
    """
    Orchestrates Hybrid Retrieval by combining ChromaDB Vector search and BM25 Lexical search.
    """
    if not query:
        return []

    v_top_k = vector_top_k or settings.VECTOR_TOP_K
    b_top_k = bm25_top_k or settings.BM25_TOP_K
    h_top_k = hybrid_top_k or settings.HYBRID_TOP_K
    rrf_k = settings.RRF_K

    # Perform Vector & Lexical searches
    vector_candidates = search_knowledge_base(query, top_k=v_top_k)
    bm25_candidates = bm25_service.search(query, top_k=b_top_k)

    # Perform Reciprocal Rank Fusion
    fused_candidates = reciprocal_rank_fusion(
        vector_results=vector_candidates,
        bm25_results=bm25_candidates,
        k=rrf_k,
        top_k=h_top_k
    )

    print(f"\n[HYBRID RETRIEVAL]")
    print(f"Query: '{query}'")
    print(f"Vector candidates: {len(vector_candidates)}")
    print(f"BM25 candidates: {len(bm25_candidates)}")
    print(f"Fused candidates: {len(fused_candidates)}")
    print(f"Final candidates: {[c['chunk_id'] for c in fused_candidates[:5]]}\n")

    return fused_candidates

