# test_token_count.py
from services.token_service import count_tokens

sample_text = (
    "Google Gemini is a highly capable AI model. It can process text, audio, images, and video. "
    "It is built on transformer architecture. Gemini comes in different sizes like Nano, Flash, Pro, and Ultra. "
    "Flash is optimized for speed and cost efficiency."
)

token_count = count_tokens(sample_text)
print(f"Sample text ({len(sample_text)} characters):")
print(f"'{sample_text}'")
print(f"\nCalculated Token Count: {token_count}")

# Basic assertion verification
assert token_count > 0, "Token count should be greater than 0"
assert count_tokens("") == 0, "Empty string should return 0 tokens"
print("\nVerification Passed Successfully!")
