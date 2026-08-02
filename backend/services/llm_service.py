# services/llm_service.py
# This file handles all communication with the Google Gemini AI model.

import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from typing import List


# Load environment variables from a .env file located in the root directory
load_dotenv()

def generate_response(context_chunks: List[str], question: str) -> str:
    """
    Generates a highly accurate response using Google Gemini.
    It strictly uses ONLY the provided context chunks to answer the question.
    
    Args:
        context_chunks (List[str]): The relevant text chunks retrieved from the vector database.
        question (str): The specific question the user asked about the PDF.
        
    Returns:
        str: The generated answer from the AI.
        
    Raises:
        ValueError: If inputs are invalid or the API key is missing.
        Exception: If the Gemini API request fails.
    """
    
    # 1. Error Handling: Check for missing API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing in the .env file. Please add it.")

    # 2. Error Handling: Check for empty context
    if not context_chunks:
        raise ValueError("No context chunks provided. Cannot generate a response.")
        
    # 3. Error Handling: Check for empty user question
    if not question or not question.strip():
        raise ValueError("The user question is empty. Please ask a valid question.")

    try:
        # Initialize the Gemini client using the latest SDK
        client = genai.Client(api_key=api_key)

        # 4. Strict System Instructions via SDK Config
        system_instruction = (
            "You are an intelligent and accurate document-answering AI assistant. "
            "Your main job is to answer the user's question based on the provided context chunks. "
            "The context chunks may include page numbers (e.g., [Page 4]). You should cite page numbers if helpful. "
            "Do NOT hallucinate or guess facts outside the provided context. "
            "However, you may summarize, synthesize, or explain concepts found within the context. "
            "If the information is completely unrelated or missing, state clearly that the answer cannot be found in the document."
        )

        # 5. Create a clean, tagged prompt
        combined_context = "\n\n--- Chunk ---\n\n".join(context_chunks)
        prompt = f"""
Here are the relevant text chunks extracted from the user's PDF document:
<context>
{combined_context}
</context>

Based on the <context> above, please answer the following question:
{question}
"""

        # 6. Debug Prints (as requested)
        print("\n=== DEBUG INFO ===")
        print(f"USER QUESTION: {question}")
        # Only print the first 1000 characters so we don't flood the terminal
        print(f"CONTEXT (first 1000 chars):\n{combined_context[:1000]}...")
        print(f"COMPLETE PROMPT:\n{prompt}")
        print("==================\n")

        # 7. Send request to Gemini
        # We pass our system_instruction via the GenerateContentConfig object.
        # We also set temperature to 0.0 to make the AI extremely factual and literal, reducing creativity/hallucinations.
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.0  
            )
        )

        # 8. Print the raw response for debugging
        print(f"\n=== RAW GEMINI RESPONSE ===\n{response.text}\n===========================\n")

        return response.text

    except Exception as e:
        # Catch network or API limits
        raise Exception(f"Failed to communicate with Gemini API: {str(e)}")

def generate_summary(pdf_text: str, summary_type: str) -> str:
    """
    Generates a high-quality summary of the provided PDF text using Google Gemini.
    
    Args:
        pdf_text (str): The extracted text from the PDF document.
        summary_type (str): The requested size/detail of the summary (minimum, medium, large).
        
    Returns:
        str: The generated summary.
        
    Raises:
        ValueError: If inputs are invalid or the API key is missing.
        Exception: If the Gemini API request fails.
    """
    
    # 1. Error Handling
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing in the .env file. Please add it.")

    if not pdf_text or not pdf_text.strip():
        raise ValueError("The provided PDF text is empty. Cannot generate a summary.")
        
    valid_types = ["small", "medium", "large"]
    if summary_type not in valid_types:
        raise ValueError(f"Invalid summary_type. Must be one of: {', '.join(valid_types)}")

    try:
        # 2. Initialize Client
        client = genai.Client(api_key=api_key)

        # 3. Dynamic System Instructions based on summary_type
        base_instruction = (
            "You are an expert summarization AI. Your ONLY job is to summarize the provided PDF text. "
            "Do NOT use any outside knowledge. Do NOT hallucinate. "
            "If the provided text is too short, generate the best possible summary from what is available. "
        )
        
        style_instruction = ""
        if summary_type == "small":
            style_instruction = (
                "Create a small summary: Provide 3-5 bullet points focusing ONLY on the most important ideas. "
                "Keep the total length under 100 words."
            )
        elif summary_type == "medium":
            style_instruction = (
                "Create a medium summary: Write around 200-300 words explaining the important concepts with some details. "
                "Use bullet points where appropriate."
            )
        elif summary_type == "large":
            style_instruction = (
                "Create a large summary: Write around 500-700 words covering all major topics from the PDF. "
                "Use headings, subheadings, and bullet points to maintain logical flow. Preserve important technical terms."
            )
            
        system_instruction = base_instruction + style_instruction

        # 4. Prompt Generation
        prompt = f"""
Please provide a {summary_type} summary of the following text extracted from a PDF document:
<pdf_text>
{pdf_text}
</pdf_text>
"""

        print(f"\n=== GENERATING {summary_type.upper()} SUMMARY ===")
        print(f"PDF TEXT (first 500 chars):\n{pdf_text[:500]}...")

        # 5. API Request
        # Temperature slightly higher (0.2) than QA (0.0) to allow for better phrasing while remaining factual
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2  
            )
        )

        print("=== SUMMARY GENERATED SUCESSFULLY ===\n")
        return response.text

    except Exception as e:
        raise Exception(f"Failed to communicate with Gemini API for summarization: {str(e)}")
