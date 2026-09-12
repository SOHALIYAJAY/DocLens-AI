# test_step2_3_4_hybrid.py
import os
import sys

from services.pdf_service import extract_text_from_pdf, generate_document_id
from services.chunk_service import chunk_pages_with_metadata
from services.vector_service import add_to_knowledge_base, clear_knowledge_base
from services.bm25_service import bm25_service
from services.hybrid_retriever_service import retrieve_hybrid_chunks, reciprocal_rank_fusion
from services.retriever_service import retrieve_relevant_chunks
from core.config import settings

def run_hybrid_tests():
    print("\n========== RUNNING STEPS 2, 3 & 4 (BM25 + HYBRID RRF) TESTS ==========")
    
    # 1. Prepare sample chunks with exact keywords, dates, percentages, and technical terms
    doc_id = "doc_test_hybrid_123"
    sample_chunks = [
        {
            "document_id": doc_id,
            "document_name": "financial_report.pdf",
            "page_number": 12,
            "page_start": 12,
            "page_end": 12,
            "section": "Financial Performance",
            "heading": "Gross Margin Overview",
            "chapter": "Chapter 2: Financials",
            "subsection": "2.1 FY2025 Margin",
            "parent_section": "Financial Performance",
            "chunk_id": f"{doc_id}_p12_c001",
            "content_type": "text",
            "figure_id": "",
            "table_id": "",
            "caption": "",
            "source_type": "pdf",
            "page": 12,
            "text": "Gross margin increased by 18.7% in FY2025 due to cost optimization and higher high-margin software sales."
        },
        {
            "document_id": doc_id,
            "document_name": "financial_report.pdf",
            "page_number": 13,
            "page_start": 13,
            "page_end": 13,
            "section": "Revenue Analysis",
            "heading": "Annual Revenue",
            "chapter": "Chapter 2: Financials",
            "subsection": "2.2 Revenue Breakdown",
            "parent_section": "Revenue Analysis",
            "chunk_id": f"{doc_id}_p13_c002",
            "content_type": "table",
            "figure_id": "",
            "table_id": "table_1",
            "caption": "Annual Revenue Table",
            "source_type": "pdf",
            "page": 13,
            "text": "| Year | Revenue | Operating Expenses |\n| --- | --- | --- |\n| 2024 | $12.5M | $8.2M |\n| 2025 | $15.8M | $9.1M |"
        },
        {
            "document_id": doc_id,
            "document_name": "financial_report.pdf",
            "page_number": 14,
            "page_start": 14,
            "page_end": 14,
            "section": "System Architecture",
            "heading": "Microservices Design",
            "chapter": "Chapter 3: Engineering",
            "subsection": "3.1 Architecture",
            "parent_section": "System Architecture",
            "chunk_id": f"{doc_id}_p14_c003",
            "content_type": "text",
            "figure_id": "figure_1",
            "table_id": "",
            "caption": "Architecture Diagram",
            "source_type": "pdf",
            "page": 14,
            "text": "The DocLens-AI system relies on a FastAPI Python backend paired with ChromaDB vector search and BM25 lexical indexing."
        }
    ]

    # 2. Test BM25 Indexing & Search
    bm25_service.clear_index()
    bm25_service.add_documents(sample_chunks)
    
    # Exact keyword test 1: "gross margin 18.7% FY2025"
    bm25_res = bm25_service.search("gross margin 18.7% FY2025", top_k=2)
    print(f"BM25 Search for 'gross margin 18.7% FY2025': {len(bm25_res)} hits")
    assert len(bm25_res) > 0, "BM25 failed on exact keyword search"
    assert bm25_res[0]["chunk_id"] == f"{doc_id}_p12_c001"
    assert "18.7%" in bm25_res[0]["text"]
    print(f"  [PASS] Top BM25 match chunk ID: {bm25_res[0]['chunk_id']} (score: {bm25_res[0]['bm25_score']:.4f})")

    # Exact keyword test 2: "Operating Expenses $8.2M"
    bm25_res_table = bm25_service.search("Operating Expenses $8.2M", top_k=1)
    assert len(bm25_res_table) > 0
    assert bm25_res_table[0]["chunk_id"] == f"{doc_id}_p13_c002"
    print(f"  [PASS] Table match chunk ID: {bm25_res_table[0]['chunk_id']}")

    # 3. Test Vector + BM25 Reciprocal Rank Fusion (RRF)
    clear_knowledge_base()
    add_to_knowledge_base(sample_chunks)

    hybrid_hits = retrieve_hybrid_chunks("What was the gross margin increase in FY2025?")
    print(f"Hybrid Retrieval returned {len(hybrid_hits)} fused candidates.")
    assert len(hybrid_hits) > 0, "Hybrid retrieval returned empty results"
    top_hit = hybrid_hits[0]
    print(f"  [PASS] Top Hybrid RRF match chunk ID: {top_hit.get('chunk_id')} (RRF Score: {top_hit.get('rrf_score'):.4f})")
    assert top_hit.get("chunk_id") == f"{doc_id}_p12_c001"

    # 4. Test retriever_service formatting
    formatted = retrieve_relevant_chunks("gross margin FY2025")
    print(f"Retriever Service returned {len(formatted)} formatted strings.")
    assert len(formatted) > 0
    print(f"Sample formatted string snippet:\n{formatted[0][:150]}")
    assert "[Page 12]" in formatted[0]
    assert "[Section: Financial Performance]" in formatted[0]

    # 5. Check configuration constants
    assert settings.VECTOR_TOP_K == 10
    assert settings.BM25_TOP_K == 10
    assert settings.HYBRID_TOP_K == 15
    assert settings.RRF_K == 60
    print("  [PASS] Config settings verified.")

    print("\n========== STEPS 2, 3 & 4 (BM25 + HYBRID RRF) TESTS PASSED SUCCESSFULLY! ==========\n")

if __name__ == "__main__":
    run_hybrid_tests()
