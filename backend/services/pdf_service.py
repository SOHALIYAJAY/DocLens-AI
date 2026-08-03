# services/pdf_service.py
import io
import os
import tempfile
import time
import base64
from anthropic import Anthropic, APIError, APIConnectionError
from dotenv import load_dotenv
import fitz  # PyMuPDF text preserverd properly structurewise

load_dotenv()

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts raw text from a PDF file. Uses pypdf for normal PDFs and falls back
    to Gemini OCR for scanned PDFs.
    
    Args:
        file_bytes (bytes): The raw bytes of the uploaded PDF file.
        
    Returns:
        list: A list of dictionaries, each containing 'page' (int) and 'text' (str).
    """
    try:
        # 1. Attempt fast extraction with PyMuPDF
        extracted_pages = []
        total_text_length = 0
        
        # fitz can open from stream/bytes directly
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        num_pages = len(doc)
        
        for i in range(num_pages):
            page = doc.load_page(i)
            # Use 'text' block for clean structural extraction
            text = page.get_text("text")
            if text:
                # Remove excessive newlines but keep paragraph structure
                clean_text = "\n".join([line.strip() for line in text.split("\n") if line.strip()])
                if clean_text:
                    extracted_pages.append({"page": i + 1, "text": clean_text})
                    total_text_length += len(clean_text)
                    
        doc.close()
        
        # 2. Check if we need to fallback to OCR
        # If the extracted text is very short compared to the number of pages, it's likely scanned.
        if total_text_length < (num_pages * 50) or total_text_length < 100:
            print("Scanned PDF detected (low text volume). Falling back to Claude OCR via AgentRouter...")
            
            api_key = os.getenv("AGENTROUTER_API_KEY")
            if not api_key:
                raise ValueError("AGENTROUTER_API_KEY is missing. Cannot perform OCR.")
                
            base_url = os.getenv("AGENTROUTER_BASE_URL", "https://agentrouter.org")
            model_name = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
            
            client = Anthropic(api_key=api_key, base_url=base_url)
            
            print("Extracting text via Claude (AgentRouter)...")
            pdf_base64 = base64.b64encode(file_bytes).decode("utf-8")
            
            try:
                response = client.beta.messages.create(
                    model=model_name,
                betas=["pdfs-2024-09-25"],
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": (
                                    "This is a scanned PDF document. Please transcribe all the text exactly as it appears. "
                                    "Do not summarize or omit anything. Maintain the original structure where possible."
                                )
                            }
                        ]
                    }
                ]
            )
            
            except APIConnectionError as e:
                raise Exception(f"Failed to connect to AgentRouter API during OCR: {str(e)}")
            except APIError as e:
                raise Exception(f"AgentRouter API returned an error during OCR: {str(e)}")
            except Exception as e:
                raise Exception(f"An unexpected error occurred during OCR extraction: {str(e)}")
            
            final_text = ""
            for block in response.content:
                if getattr(block, "type", "") == "text":
                    final_text += block.text
            
            extracted_text = final_text.strip()
            extracted_pages = [{"page": 1, "text": extracted_text}]
            print("OCR Extraction complete.")
                    
        return extracted_pages
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")

