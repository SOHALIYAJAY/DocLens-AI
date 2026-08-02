import requests

# Test 1: Sending old Q&A payload to new /summarize endpoint
payload = {
    "pdf_text": "Manoj is a person.",
    "question": "Who is Manoj?"
}
resp = requests.post("http://127.0.0.1:8000/summarize", json=payload)
print("TEST 1 (/summarize with Q&A payload):", resp.status_code, resp.text)

# Test 2: Sending Q&A payload to /qa endpoint
resp2 = requests.post("http://127.0.0.1:8000/qa", json=payload)
print("TEST 2 (/qa with Q&A payload):", resp2.status_code, resp2.text)
