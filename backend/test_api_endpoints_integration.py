# test_api_endpoints_integration.py
import requests
import os

BASE_URL = "http://127.0.0.1:8000"

def test_endpoints():
    print("\n========== TESTING API ENDPOINTS INTEGRATION ==========")
    
    # 1. Test Root Endpoint
    r_root = requests.get(f"{BASE_URL}/")
    print("GET / :", r_root.status_code, r_root.json())
    assert r_root.status_code == 200
    
    # 2. Test Local PDF Upload Endpoint (/upload-local-pdf)
    test_pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test.pdf"))
    r_upload = requests.post(
        f"{BASE_URL}/upload-local-pdf",
        json={"file_path": test_pdf_path}
    )
    print("POST /upload-local-pdf :", r_upload.status_code, r_upload.json())
    assert r_upload.status_code == 200
    res_upload = r_upload.json()
    assert res_upload["success"] is True
    assert res_upload["num_chunks"] >= 1
    
    # 3. Test Chat Q&A Endpoint (/chat)
    r_chat = requests.post(
        f"{BASE_URL}/chat",
        json={"question": "What is this document about?"}
    )
    print("POST /chat :", r_chat.status_code, r_chat.json())
    assert r_chat.status_code == 200
    assert r_chat.json()["success"] is True
    
    # 4. Test Summarize Endpoint (/summarize)
    r_sum = requests.post(
        f"{BASE_URL}/summarize",
        json={"summary_type": "medium"}
    )
    print("POST /summarize :", r_sum.status_code, "Summary snippet:", r_sum.json()["summary"][:100])
    assert r_sum.status_code == 200
    assert r_sum.json()["success"] is True
    
    print("\n========== ALL API ENDPOINTS INTEGRATION TESTS PASSED! ==========\n")

if __name__ == "__main__":
    test_endpoints()
