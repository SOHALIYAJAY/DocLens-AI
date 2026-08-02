# services/ai_service.py
# This file contains the business logic for the application.
# Right now, it returns dummy data, but later this is where you will connect 
# to OpenAI, Anthropic, or any other AI model.

def generate_dummy_summary(pdf_text: str, question: str = None) -> str:
    """
    Simulates calling an AI model by returning a dummy response.
    
    Args:
        pdf_text (str): The text extracted from the PDF.
        question (str, optional): The user's question about the PDF.
        
    Returns:
        str: A dummy AI response.
    """
    
    # We can check if a question was asked to return a slightly different dummy response
    if question:
        return f"This is a dummy AI response answering your question: '{question}'"
    
    return "This is a dummy AI response providing a summary of the PDF."
