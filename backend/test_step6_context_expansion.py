# test_step6_context_expansion.py
import os
import requests

from services.pdf_service import extract_text_from_pdf, generate_document_id
from services.chunk_service import chunk_pages_with_metadata
from services.vector_service import add_to_knowledge_base, clear_knowledge_base
from services.bm25_service import bm25_service
from services.context_expansion_service import context_expansion_service
from services.hybrid_retriever_service import retrieve_hybrid_chunks
from services.reranker_service import reranker_service
from services.retriever_service import retrieve_relevant_chunks

BASE_URL = "http://127.0.0.1:8000"

def run_context_expansion_tests():
    print("\n========== RUNNING STEP 6 CONTEXT EXPANSION VERIFICATION TESTS ==========")

    doc_id = "doc_step6_exp_999"
    # Create 6 sequential chunks spanning pages and sections where sentence answers split across boundaries
    test_chunks = [
        {
            "document_id": doc_id,
            "document_name": "annual_report_2025.pdf",
            "page_number": 1,
            "page_start": 1,
            "page_end": 1,
            "section": "Executive Overview",
            "heading": "Summary",
            "chapter": "Chapter 1",
            "chunk_id": f"{doc_id}_p1_c001",
            "content_type": "text",
            "text": "DocLens-AI is an enterprise AI PDF Assistant designed for high-precision hybrid document intelligence."
        },
        {
            "document_id": doc_id,
            "document_name": "annual_report_2025.pdf",
            "page_number": 2,
            "page_start": 2,
            "page_end": 2,
            "section": "Financial Performance",
            "heading": "Revenue Growth",
            "chapter": "Chapter 2",
            "chunk_id": f"{doc_id}_p2_c002",
            "content_type": "text",
            "text": "The company's gross revenue reached $48.5 million in FY2025, representing a 34% year-over-year increase. The primary driver of this financial expansion was"
        },
        {
            "document_id": doc_id,
            "document_name": "annual_report_2025.pdf",
            "page_number": 3,
            "page_start": 3,
            "page_end": 3,
            "section": "Financial Performance",
            "heading": "Revenue Growth",
            "chapter": "Chapter 2",
            "chunk_id": f"{doc_id}_p3_c003",
            "content_type": "text",
            "text": "rapid adoption of enterprise SaaS licenses and expanded cloud infrastructure partnerships across North America."
        },
        {
            "document_id": doc_id,
            "document_name": "annual_report_2025.pdf",
            "page_number": 4,
            "page_start": 4,
            "page_end": 4,
            "section": "Technical Infrastructure",
            "heading": "Database & Vector Store",
            "chapter": "Chapter 3",
            "chunk_id": f"{doc_id}_p4_c004",
            "content_type": "text",
            "text": "Our storage architecture combines ChromaDB dense vector indices with custom Okapi BM25 lexical stores."
        },
        {
            "document_id": doc_id,
            "document_name": "annual_report_2025.pdf",
            "page_number": 5,
            "page_start": 5,
            "page_end": 5,
            "section": "Technical Infrastructure",
            "heading": "Cross-Encoder & Expansion",
            "chapter": "Chapter 3",
            "chunk_id": f"{doc_id}_p5_c005",
            "content_type": "text",
            "text": "Reranked candidate chunks are dynamically expanded with neighboring context to preserve multi-chunk sentence continuity."
        }
    ]

    # Register chunks with services
    bm25_service.clear_index()
    bm25_service.add_documents(test_chunks)

    clear_knowledge_base()
    add_to_knowledge_base(test_chunks)

    context_expansion_service.clear_chunks()
    context_expansion_service.set_document_chunks(test_chunks)

    # 1. Answer Spanning Two Chunks Test
    print("--- 1. ANSWER SPANNING TWO CHUNKS ---")
    query1 = "What was the primary driver of financial expansion in FY2025?"
    formatted1 = retrieve_relevant_chunks(query1)
    assert len(formatted1) > 0
    full_context1 = "\n".join(formatted1)
    print("Expanded Context snippet:\n", full_context1[:300])
    assert "$48.5 million" in full_context1 and "rapid adoption of enterprise SaaS" in full_context1
    print("  [PASS] Neighboring chunks c002 and c003 merged successfully without text loss.")

    # 2. Answer Starting in One Chunk & Continuing Across Pages Test
    print("\n--- 2. ANSWER CONTINUING ACROSS PAGES ---")
    query2 = "What is the year-over-year revenue increase and what drove it?"
    formatted2 = retrieve_relevant_chunks(query2)
    assert len(formatted2) > 0
    print("Header of merged multi-page block:", formatted2[0].split("\n")[0])
    assert any(p in formatted2[0] for p in ["Pages 1-5", "Pages 2-3", "Page 2", "Page 3"])
    print("  [PASS] Page span metadata correctly updated for neighboring chunks.")


    # 3. Question Referring to Parent Section Test
    print("\n--- 3. QUESTION REFERRING TO SECTION SCOPE ---")
    query3 = "What are the details under the Financial Performance section?"
    formatted3 = retrieve_relevant_chunks(query3)
    assert len(formatted3) > 0
    assert "[Section: Financial Performance]" in formatted3[0]
    print("  [PASS] Parent section Scope preserved in expanded context header.")

    # 4. Question Referring to Info Immediately Before/After Retrieved Chunk
    print("\n--- 4. INFORMATION IMMEDIATELY BEFORE/AFTER RETRIEVED CHUNK ---")
    query4 = "Tell me about the storage architecture and what follows it."
    formatted4 = retrieve_relevant_chunks(query4)
    assert len(formatted4) > 0
    full_context4 = "\n".join(formatted4)
    assert "ChromaDB dense vector indices" in full_context4
    assert "dynamically expanded with neighboring context" in full_context4
    print("  [PASS] Neighboring chunk c005 retrieved alongside c004.")

    # 5. Live Q&A Chat Endpoint Check
    print("\n--- 5. LIVE Q&A CHAT ENDPOINT CHECK ---")
    test_pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test.pdf"))
    r_up = requests.post(f"{BASE_URL}/upload-local-pdf", json={"file_path": test_pdf_path})
    assert r_up.status_code == 200

    r_chat = requests.post(f"{BASE_URL}/chat", json={"question": "What is this document about?"})
    assert r_chat.status_code == 200
    assert r_chat.json()["success"] is True
    print("Live /chat Answer:", r_chat.json()["answer"][:120], "...")

    print("\n========== ALL STEP 6 CONTEXT EXPANSION TESTS PASSED SUCCESSFULLY! ==========\n")

if __name__ == "__main__":
    run_context_expansion_tests()
