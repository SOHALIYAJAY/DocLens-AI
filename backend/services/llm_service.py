# services/llm_service.py
# This file handles all communication with the Anthropic Claude AI model via AgentRouter.

import os
from anthropic import Anthropic, APIError, APIConnectionError
from dotenv import load_dotenv
from typing import List

# Load environment variables from a .env file located in the root directory
load_dotenv()

def get_agentrouter_client() -> Anthropic:
    api_key = os.getenv("AGENTROUTER_API_KEY")
    if not api_key:
        raise ValueError("AGENTROUTER_API_KEY is missing in the .env file. Please add it.")
        
    base_url = os.getenv("AGENTROUTER_BASE_URL", "https://agentrouter.org")
    return Anthropic(api_key=api_key, base_url=base_url)

def get_claude_model() -> str:
    return os.getenv("CLAUDE_MODEL", "claude-opus-4-8")


def generate_response(context_chunks: List[str], question: str) -> str:
    """
    Generates a highly accurate response using Anthropic Claude via AgentRouter.
    It strictly uses ONLY the provided context chunks to answer the question.
    
    Args:
        context_chunks (List[str]): The relevant text chunks retrieved from the vector database.
        question (str): The specific question the user asked about the PDF.
        
    Returns:
        str: The generated answer from the AI.
        
    Raises:
        ValueError: If inputs are invalid or the API key is missing.
        Exception: If the API request fails.
    """
    
    # 1. Error Handling: Check for empty context
    if not context_chunks:
        raise ValueError("No context chunks provided. Cannot generate a response.")
        
    # 2. Error Handling: Check for empty user question
    if not question or not question.strip():
        raise ValueError("The user question is empty. Please ask a valid question.")

    try:
        # 3. Initialize the Anthropic client using AgentRouter config
        client = get_agentrouter_client()
        model_name = get_claude_model()

        # 4. Strict System Instructions
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

        # 6. Debug Prints
        print("\n=== DEBUG INFO ===")
        print(f"USER QUESTION: {question}")
        print(f"CONTEXT (first 1000 chars):\n{combined_context[:1000]}...")
        print(f"COMPLETE PROMPT:\n{prompt}")
        print("==================\n")

        # 7. Send request to Claude via AgentRouter
        response = client.messages.create(
            model=model_name,
            max_tokens=1024,
            temperature=0.0,
            system=system_instruction,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # 8. Print the raw response for debugging
        final_text = ""
        for block in response.content:
            if getattr(block, "type", "") == "text":
                final_text += block.text
                
        print(f"\n=== RAW CLAUDE RESPONSE ===\n{final_text}\n===========================\n")

        return final_text

    except APIConnectionError as e:
        raise Exception(f"Failed to connect to AgentRouter API: {str(e)}")
    except APIError as e:
        raise Exception(f"AgentRouter API returned an error: {str(e)}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred during generate_response: {str(e)}")


def generate_summary(pdf_text: str, summary_type: str) -> str:
    """
    Generates a high-quality summary of the provided PDF text using Anthropic Claude via AgentRouter.
    
    Args:
        pdf_text (str): The extracted text from the PDF document.
        summary_type (str): The requested size/detail of the summary (small, medium, large).
        
    Returns:
        str: The generated summary.
        
    Raises:
        ValueError: If inputs are invalid or the API key is missing.
        Exception: If the API request fails.
    """
    
    if not pdf_text or not pdf_text.strip():
        raise ValueError("The provided PDF text is empty. Cannot generate a summary.")
        
    valid_types = ["small", "medium", "large"]
    if summary_type not in valid_types:
        raise ValueError(f"Invalid summary_type. Must be one of: {', '.join(valid_types)}")

    try:
        # 1. Initialize Client via AgentRouter config
        client = get_agentrouter_client()
        model_name = get_claude_model()

        # 2. Dynamic System Instructions based on summary_type
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

        # 3. Prompt Generation
        prompt = f"""
Please provide a {summary_type} summary of the following text extracted from a PDF document:
<pdf_text>
{pdf_text}
</pdf_text>
"""

        print(f"\n=== GENERATING {summary_type.upper()} SUMMARY ===")
        print(f"PDF TEXT (first 500 chars):\n{pdf_text[:500]}...")

        # 4. API Request
        response = client.messages.create(
            model=model_name,
            max_tokens=2048,
            temperature=0.2,
            system=system_instruction,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        final_text = ""
        for block in response.content:
            if getattr(block, "type", "") == "text":
                final_text += block.text
                
        print("=== SUMMARY GENERATED SUCCESSFULLY ===\n")
        return final_text

    except APIConnectionError as e:
        raise Exception(f"Failed to connect to AgentRouter API for summarization: {str(e)}")
    except APIError as e:
        raise Exception(f"AgentRouter API returned an error for summarization: {str(e)}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred during generate_summary: {str(e)}")

