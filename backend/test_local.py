import requests

payload = {
    "pdf_text": "Manoj is a person.",
    "question": "Who is Manoj?"
}
resp = requests.post("http://127.0.0.1:8001/summarize", json=payload)
print(resp.status_code)
print(resp.json())
