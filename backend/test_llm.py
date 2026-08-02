from services.llm_service import generate_response

try:
    print("Testing generate_response...")
    ans = generate_response("This is a test PDF document.", "What kind of document is this?")
    print("SUCCESS! Answer:", ans)
except Exception as e:
    print("ERROR CAUGHT:", type(e).__name__, str(e))
