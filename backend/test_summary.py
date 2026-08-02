from services.llm_service import generate_summary

pdf = "Google Gemini is a highly capable AI model. It can process text, audio, images, and video. It is built on transformer architecture. Gemini comes in different sizes like Nano, Flash, Pro, and Ultra. Flash is optimized for speed and cost efficiency."
try:
    print("Testing minimum summary...")
    print(generate_summary(pdf, "minimum"))
    print("\nSUCCESS!")
except Exception as e:
    print("ERROR:", str(e))
