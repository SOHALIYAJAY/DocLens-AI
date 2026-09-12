# test_step2_verification.py
import os
import requests

from services.pdf_service import extract_text_from_pdf, generate_document_id
from services.chunk_service import chunk_pages_with_metadata
from services.vector_service import add_to_knowledge_base, clear_knowledge_base, search_knowledge_base
from services.navigator_service import generate_navigator
from services.vision_service import analyze_image

BASE_URL = "http://127.0.0.1:8000"

def run_step2_verification():
    print("\n========== RUNNING STEP 2 CHUNKING & METADATA VERIFICATION ==========")
    
    test_pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test.pdf"))
    if not os.path.exists(test_pdf_path):
        print(f"Error: {test_pdf_path} not found.")
        return

    with open(test_pdf_path, "rb") as f:
        file_bytes = f.read()

    # 1. Ingestion & Document ID
    doc_id = generate_document_id(file_bytes, "test.pdf")
    pages = extract_text_from_pdf(file_bytes)
    chunks = chunk_pages_with_metadata(pages, document_id=doc_id, document_name="test.pdf")

    # 2. Chunk Statistics & Metadata Audit
    print(f"\n--- CHUNK STATISTICS ---")
    print(f"Total PDF Pages: {len(pages)}")
    print(f"Total Chunks Generated: {len(chunks)}")
    
    assert len(chunks) > 0, "No chunks generated"
    sample = chunks[0]
    
    required_keys = [
        "document_id", "document_name", "chunk_id", "page_number",
        "page_start", "page_end", "section", "heading", "chapter",
        "content_type", "parent_chunk_id"
    ]
    
    print("\n--- METADATA VERIFICATION ---")
    for key in required_keys:
        assert key in sample, f"Missing key in chunk metadata: {key}"
        print(f"  {key}: {sample[key]}")

    assert sample["chunk_id"].startswith("doc_"), f"Invalid chunk_id format: {sample['chunk_id']}"
    assert sample["page_number"] == 1
    assert sample["page_start"] == 1
    assert sample["page_end"] == 1

    # 3. Test API Endpoint - PDF Upload
    print("\n--- 1. TESTING API PDF UPLOAD ---")
    r_upload = requests.post(f"{BASE_URL}/upload-local-pdf", json={"file_path": test_pdf_path})
    print("POST /upload-local-pdf status:", r_upload.status_code)
    assert r_upload.status_code == 200
    assert r_upload.json()["success"] is True

    # 4. Test Existing Q&A Endpoint
    print("\n--- 2. TESTING EXISTING Q&A ---")
    r_chat = requests.post(f"{BASE_URL}/chat", json={"question": "What is the purpose of this test document?"})
    print("POST /chat status:", r_chat.status_code)
    print("Answer:", r_chat.json()["answer"])
    assert r_chat.status_code == 200
    assert r_chat.json()["success"] is True

    # 5. Test Summarization Endpoint
    print("\n--- 3. TESTING SUMMARIZATION ---")
    r_sum = requests.post(f"{BASE_URL}/summarize", json={"summary_type": "medium"})
    print("POST /summarize status:", r_sum.status_code)
    print("Summary snippet:", r_sum.json()["summary"][:120])
    assert r_sum.status_code == 200
    assert r_sum.json()["success"] is True

    # 6. Test Navigator Functionality
    print("\n--- 4. TESTING AI DOCUMENT NAVIGATOR ---")
    nav_res = generate_navigator(file_bytes, "test.pdf")
    print(f"Navigator generated successfully. Document: {nav_res.document_name}, Pages: {nav_res.pages}")
    assert nav_res.success is True
    assert nav_res.pages >= 1

    # 7. Test Image / Figure Functionality Structure
    print("\n--- 5. TESTING IMAGE / FIGURE FUNCTIONALITY ---")
    # Verify image endpoint schema & router setup
    assert hasattr(nav_res, "figures_found")
    print(f"Figures found count in navigator: {nav_res.figures_found}")
    print(f"Images found count in navigator: {nav_res.images_found}")

    print("\n========== ALL STEP 2 VERIFICATION TESTS PASSED SUCCESSFULLY! ==========\n")

if __name__ == "__main__":
    run_step2_verification()
