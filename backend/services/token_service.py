# services/token_service.py
import tiktoken

def count_tokens(text: str, model_encoding: str = "cl100k_base") -> int:
    """
    Counts the approximate number of tokens in a given string using tiktoken BPE encoding.
    Uses 'cl100k_base' by default, which is appropriate for modern LLMs and Groq models.
    
    Args:
        text (str): The text string to tokenize and count.
        model_encoding (str): The tiktoken encoding scheme. Defaults to 'cl100k_base'.
        
    Returns:
        int: Total token count.
    """
    if not text:
        return 0

    try:
        encoding = tiktoken.get_encoding(model_encoding)
        return len(encoding.encode(text))
    except Exception as e:
        # Fallback estimation (1 token approx 4 characters) if encoding fails
        print(f"Token counting fallback triggered: {e}")
        return max(1, len(text) // 4)
