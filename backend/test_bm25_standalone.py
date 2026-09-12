# test_bm25_standalone.py
import os
import sys

from services.bm25_service import bm25_service
from services.vector_service import add_to_knowledge_base, clear_knowledge_base, search_knowledge_base
from services.retriever_service import retrieve_relevant_chunks

def run_bm25_tests():
    print("\n========== RUNNING BM25 LEXICAL RETRIEVAL VERIFICATION TESTS ==========")

    doc_id = "doc_bm25_test_999"
    test_chunks = [
        {
            "document_id": doc_id,
            "document_name": "annual_report.pdf",
            "page_number": 5,
            "page_start": 5,
            "page_end": 5,
            "section": "Financial Highlights",
            "heading": "Gross Margin",
            "chapter": "Financials",
            "chunk_id": f"{doc_id}_p5_c001",
            "content_type": "text",
            "text": "Gross margin expanded by 18.7% in FY2025 driven by cloud software growth."
        },
        {
            "document_id": doc_id,
            "document_name": "annual_report.pdf",
            "page_number": 8,
            "page_start": 8,
            "page_end": 8,
            "section": "Technical Architecture",
            "heading": "Database Infrastructure",
            "chapter": "Engineering",
            "chunk_id": f"{doc_id}_p8_c002",
            "content_type": "text",
            "text": "DocLens-AI utilizes ChromaDB vector search and Okapi BM25 lexical indexing."
        },
        {
            "document_id": doc_id,
            "document_name": "annual_report.pdf",
            "page_number": 12,
            "page_start": 12,
            "page_end": 12,
            "section": "Executive Management",
            "heading": "Leadership",
            "chapter": "Governance",
            "chunk_id": f"{doc_id}_p12_c003",
            "content_type": "text",
            "text": "Dr. Aris Thorne was appointed Chief Technology Officer in October 2024."
        }
    ]

    # Populate BM25 and ChromaDB with the same chunks
    bm25_service.clear_index()
    bm25_service.add_documents(test_chunks)

    clear_knowledge_base()
    add_to_knowledge_base(test_chunks)

    print("\n--- 1. EXACT KEYWORD QUESTION ---")
    res1 = bm25_service.search("Chief Technology Officer Dr. Aris Thorne", top_k=2)
    assert len(res1) > 0
    assert res1[0]["chunk_id"] == f"{doc_id}_p12_c003"
    print("  [PASS] Exact Keyword query matched chunk:", res1[0]["chunk_id"])

    print("\n--- 2. NUMBER QUESTION ---")
    res2 = bm25_service.search("18.7% FY2025", top_k=2)
    assert len(res2) > 0
    assert res2[0]["chunk_id"] == f"{doc_id}_p5_c001"
    print("  [PASS] Number query matched chunk:", res2[0]["chunk_id"])

    print("\n--- 3. TECHNICAL TERM QUESTION ---")
    res3 = bm25_service.search("ChromaDB vector search Okapi BM25", top_k=2)
    assert len(res3) > 0
    assert res3[0]["chunk_id"] == f"{doc_id}_p8_c002"
    print("  [PASS] Technical term query matched chunk:", res3[0]["chunk_id"])

    print("\n--- 4. NORMAL SEMANTIC QUESTION (Vector RAG Check) ---")
    vec_res = search_knowledge_base("Who is the chief technology officer?", top_k=2)
    assert len(vec_res) > 0
    print("  [PASS] Vector RAG returned:", vec_res[0]["text"][:60])

    print("\n========== ALL BM25 VERIFICATION TESTS PASSED SUCCESSFULLY! ==========\n")

if __name__ == "__main__":
    run_bm25_tests()
