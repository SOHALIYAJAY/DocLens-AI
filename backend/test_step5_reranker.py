# test_step5_reranker.py
import os
import requests

from services.pdf_service import extract_text_from_pdf, generate_document_id
from services.chunk_service import chunk_pages_with_metadata
from services.vector_service import add_to_knowledge_base, clear_knowledge_base
from services.bm25_service import bm25_service
from services.hybrid_retriever_service import retrieve_hybrid_chunks
from services.reranker_service import reranker_service
from services.retriever_service import retrieve_relevant_chunks
from core.config import settings

BASE_URL = "http://127.0.0.1:8000"

def run_reranker_tests():
    print("\n========== RUNNING STEP 5 CROSS-ENCODER RERANKER VERIFICATION TESTS ==========")

    doc_id = "doc_step5_rerank_777"
    # Create 8 diverse chunks across 6 pages to simulate hybrid candidates
    test_chunks = [
        {
            "document_id": doc_id,
            "document_name": "multi_page_doc.pdf",
            "page_number": 1,
            "page_start": 1,
            "page_end": 1,
            "section": "Introduction",
            "heading": "Overview",
            "chapter": "Chapter 1",
            "chunk_id": f"{doc_id}_p1_c001",
            "content_type": "text",
            "text": "DocLens-AI provides an intelligent PDF assistant leveraging Hybrid RAG architecture."
        },
        {
            "document_id": doc_id,
            "document_name": "multi_page_doc.pdf",
            "page_number": 2,
            "page_start": 2,
            "page_end": 2,
            "section": "Financial Results",
            "heading": "Revenue & Operating Expenses",
            "chapter": "Chapter 2",
            "chunk_id": f"{doc_id}_p2_c002",
            "content_type": "table",
            "table_id": "table_1",
            "text": "| Metric | FY2024 | FY2025 |\n| Revenue | $12.5M | $18.7M |\n| Expenses | $8.2M | $9.1M |"
        },
        {
            "document_id": doc_id,
            "document_name": "multi_page_doc.pdf",
            "page_number": 3,
            "page_start": 3,
            "page_end": 3,
            "section": "Financial Results",
            "heading": "Gross Margin Breakdown",
            "chapter": "Chapter 2",
            "chunk_id": f"{doc_id}_p3_c003",
            "content_type": "text",
            "text": "Gross margin expanded to 68.5% in FY2025 due to software licensing growth and reduced cloud infrastructure overhead."
        },
        {
            "document_id": doc_id,
            "document_name": "multi_page_doc.pdf",
            "page_number": 4,
            "page_start": 4,
            "page_end": 4,
            "section": "Engineering Architecture",
            "heading": "Vector & BM25 Integration",
            "chapter": "Chapter 3",
            "chunk_id": f"{doc_id}_p4_c004",
            "content_type": "text",
            "text": "The vector search component employs ChromaDB while the lexical search uses a custom Okapi BM25 engine."
        },
        {
            "document_id": doc_id,
            "document_name": "multi_page_doc.pdf",
            "page_number": 5,
            "page_start": 5,
            "page_end": 5,
            "section": "Engineering Architecture",
            "heading": "Cross-Encoder Reranker",
            "chapter": "Chapter 3",
            "chunk_id": f"{doc_id}_p5_c005",
            "content_type": "text",
            "text": "Candidates from RRF fusion are evaluated by a Cross-Encoder reranker to select the top 5 most relevant context chunks."
        },
        {
            "document_id": doc_id,
            "document_name": "multi_page_doc.pdf",
            "page_number": 6,
            "page_start": 6,
            "page_end": 6,
            "section": "Executive Leadership",
            "heading": "Appointments",
            "chapter": "Chapter 4",
            "chunk_id": f"{doc_id}_p6_c006",
            "content_type": "text",
            "text": "Dr. Aris Thorne was appointed Chief Technology Officer in October 2024 to lead global AI innovation."
        }
    ]

    # Index chunks into BM25 and ChromaDB
    bm25_service.clear_index()
    bm25_service.add_documents(test_chunks)

    clear_knowledge_base()
    add_to_knowledge_base(test_chunks)

    # 1. Semantic Question Test
    print("--- 1. SEMANTIC QUESTION ---")
    query1 = "How does the system select the most relevant chunks for the LLM?"
    candidates1 = retrieve_hybrid_chunks(query1)
    reranked1 = reranker_service.rerank(query1, candidates1, top_k=settings.RERANK_TOP_K)
    print("Top reranked chunk:", reranked1[0]["chunk_id"], "| Score:", reranked1[0]["rerank_score"])
    assert len(reranked1) <= settings.RERANK_TOP_K
    assert "rerank_score" in reranked1[0]

    # 2. Exact Keyword Question Test
    print("--- 2. EXACT KEYWORD QUESTION ---")
    query2 = "Gross margin expanded to 68.5% FY2025"
    candidates2 = retrieve_hybrid_chunks(query2)
    reranked2 = reranker_service.rerank(query2, candidates2, top_k=settings.RERANK_TOP_K)
    assert len(reranked2) > 0
    assert reranked2[0]["chunk_id"] == f"{doc_id}_p3_c003"
    print("  [PASS] Top reranked exact keyword chunk matched:", reranked2[0]["chunk_id"])

    # 3. Multi-Part Question Test
    print("--- 3. MULTI-PART QUESTION ---")
    query3 = "What was the FY2025 revenue and who is the Chief Technology Officer?"
    candidates3 = retrieve_hybrid_chunks(query3)
    reranked3 = reranker_service.rerank(query3, candidates3, top_k=settings.RERANK_TOP_K)
    assert len(reranked3) > 0
    top_cids = [c["chunk_id"] for c in reranked3]
    print("Top candidate IDs for multi-part query:", top_cids)
    assert f"{doc_id}_p2_c002" in top_cids or f"{doc_id}_p6_c006" in top_cids
    print("  [PASS] Multi-part query returned expected multi-topic chunks.")

    # 4. Question Requiring Information from Different Pages Test
    print("--- 4. MULTI-PAGE INFORMATION QUESTION ---")
    query4 = "Summarize the financial revenue results on page 2 and engineering architecture on page 4."
    formatted4 = retrieve_relevant_chunks(query4)
    print(f"Retrieved {len(formatted4)} reranked formatted chunks for multi-page query.")
    assert len(formatted4) <= settings.RERANK_TOP_K
    print("Formatted Chunk 1 Header Snippet:\n", formatted4[0][:120])

    # 5. Live Q&A Chat Endpoint Test
    print("\n--- 5. LIVE Q&A CHAT ENDPOINT CHECK ---")
    test_pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test.pdf"))
    r_up = requests.post(f"{BASE_URL}/upload-local-pdf", json={"file_path": test_pdf_path})
    assert r_up.status_code == 200

    r_chat = requests.post(f"{BASE_URL}/chat", json={"question": "What is this document about?"})
    assert r_chat.status_code == 200
    assert r_chat.json()["success"] is True
    print("Live /chat Answer:", r_chat.json()["answer"][:120], "...")

    print("\n========== ALL STEP 5 CROSS-ENCODER RERANKER TESTS PASSED SUCCESSFULLY! ==========\n")

if __name__ == "__main__":
    run_reranker_tests()
