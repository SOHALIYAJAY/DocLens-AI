# test_step4_hybrid_fusion.py
import os
import requests

from services.pdf_service import extract_text_from_pdf, generate_document_id
from services.chunk_service import chunk_pages_with_metadata
from services.vector_service import add_to_knowledge_base, clear_knowledge_base
from services.bm25_service import bm25_service
from services.hybrid_retriever_service import retrieve_hybrid_chunks
from services.retriever_service import retrieve_relevant_chunks
from core.config import settings

BASE_URL = "http://127.0.0.1:8000"

def run_hybrid_fusion_tests():
    print("\n========== RUNNING STEP 4 HYBRID RRF FUSION VERIFICATION TESTS ==========")

    doc_id = "doc_step4_fusion_888"
    test_chunks = [
        {
            "document_id": doc_id,
            "document_name": "hybrid_doc.pdf",
            "page_number": 3,
            "page_start": 3,
            "page_end": 3,
            "section": "Financial Results",
            "heading": "Gross Margin",
            "chapter": "Finance",
            "chunk_id": f"{doc_id}_p3_c001",
            "content_type": "text",
            "text": "In FY2025, gross margin expanded by 18.7% due to operational efficiency and SaaS growth."
        },
        {
            "document_id": doc_id,
            "document_name": "hybrid_doc.pdf",
            "page_number": 7,
            "page_start": 7,
            "page_end": 7,
            "section": "Engineering Architecture",
            "heading": "Vector & Lexical Search",
            "chapter": "Engineering",
            "chunk_id": f"{doc_id}_p7_c002",
            "content_type": "text",
            "text": "DocLens-AI integrates ChromaDB vector search and BM25 lexical indexing for hybrid retrieval."
        },
        {
            "document_id": doc_id,
            "document_name": "hybrid_doc.pdf",
            "page_number": 10,
            "page_start": 10,
            "page_end": 10,
            "section": "Leadership & Governance",
            "heading": "Appointments",
            "chapter": "Governance",
            "chunk_id": f"{doc_id}_p10_c003",
            "content_type": "text",
            "text": "The board announced new executive leadership appointments effective October 2024."
        }
    ]

    # Populate index
    bm25_service.clear_index()
    bm25_service.add_documents(test_chunks)

    clear_knowledge_base()
    add_to_knowledge_base(test_chunks)

    # Verify configurable settings
    assert settings.VECTOR_TOP_K == 10
    assert settings.BM25_TOP_K == 10
    assert settings.HYBRID_TOP_K == 15

    # 1. Semantic Question
    print("--- 1. SEMANTIC QUESTION ---")
    res1 = retrieve_hybrid_chunks("What drives the operational efficiency and revenue growth?")
    assert len(res1) > 0
    print("  [PASS] Structured Result Sample:", {k: res1[0][k] for k in ["chunk_id", "page_number", "score", "retrieval_sources"]})
    assert "vector" in res1[0]["retrieval_sources"] or "bm25" in res1[0]["retrieval_sources"]

    # 2. Exact Keyword Question
    print("--- 2. EXACT KEYWORD QUESTION ---")
    res2 = retrieve_hybrid_chunks("Gross margin FY2025")
    assert len(res2) > 0
    assert res2[0]["chunk_id"] == f"{doc_id}_p3_c001"
    print("  [PASS] Top candidate matched chunk:", res2[0]["chunk_id"])

    # 3. Number Question
    print("--- 3. NUMBER QUESTION ---")
    res3 = retrieve_hybrid_chunks("18.7%")
    assert len(res3) > 0
    assert res3[0]["chunk_id"] == f"{doc_id}_p3_c001"
    print("  [PASS] Number query matched chunk:", res3[0]["chunk_id"])

    # 4. Date Question
    print("--- 4. DATE QUESTION ---")
    res4 = retrieve_hybrid_chunks("October 2024")
    assert len(res4) > 0
    assert res4[0]["chunk_id"] == f"{doc_id}_p10_c003"
    print("  [PASS] Date query matched chunk:", res4[0]["chunk_id"])

    # 5. Technical Terminology Question
    print("--- 5. TECHNICAL TERMINOLOGY QUESTION ---")
    res5 = retrieve_hybrid_chunks("ChromaDB vector search and BM25")
    assert len(res5) > 0
    assert res5[0]["chunk_id"] == f"{doc_id}_p7_c002"
    print("  [PASS] Technical terminology query matched chunk:", res5[0]["chunk_id"])

    # 6. Question Whose Answer Does Not Exist
    print("--- 6. UNANSWERABLE QUESTION ---")
    res6 = retrieve_hybrid_chunks("Quantum teleportation flux capacitor 9999")
    print(f"  [PASS] Unanswerable query candidates count: {len(res6)}")

    # 7. Test Live Q&A Chat Endpoint
    print("\n--- 7. LIVE Q&A ENDPOINT CHECK ---")
    test_pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test.pdf"))
    r_up = requests.post(f"{BASE_URL}/upload-local-pdf", json={"file_path": test_pdf_path})
    assert r_up.status_code == 200

    r_chat = requests.post(f"{BASE_URL}/chat", json={"question": "What is the purpose of this test document?"})
    assert r_chat.status_code == 200
    assert r_chat.json()["success"] is True
    print("Live /chat Answer:", r_chat.json()["answer"][:100], "...")

    print("\n========== ALL STEP 4 HYBRID FUSION TESTS PASSED SUCCESSFULLY! ==========\n")

if __name__ == "__main__":
    run_hybrid_fusion_tests()
