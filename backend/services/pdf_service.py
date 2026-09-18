# services/pdf_service.py
import io
import os
import tempfile
import time
import base64
from dotenv import load_dotenv
try:
    import pymupdf as fitz  # PyMuPDF
except ImportError:
    import fitz
from services.llm_service import get_groq_client, get_groq_vision_client

load_dotenv()

import hashlib
import pymupdf4llm

def generate_document_id(file_bytes: bytes, filename: str = "") -> str:
    """
    Generates a deterministic document ID string from PDF file content and filename.
    """
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    if filename:
        hasher.update(filename.encode("utf-8"))
    return f"doc_{hasher.hexdigest()[:12]}"

def extract_text_from_pdf(file_bytes: bytes) -> list:
    """
    Extracts layout-aware Markdown text from a PDF file using pymupdf4llm.
    Falls back to PyMuPDF fitz text blocks or Groq Vision OCR for scanned PDFs.
    
    Args:
        file_bytes (bytes): The raw bytes of the uploaded PDF file.
        
    Returns:
        list: A list of dictionaries, each containing 'page' (int) and 'text' (str).
    """
    try:
        extracted_pages = []
        total_text_length = 0

        # 1. Attempt layout-aware markdown extraction via pymupdf4llm
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            num_pages = len(doc)

            m_chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)
            doc.close()

            if m_chunks:
                for idx, chunk in enumerate(m_chunks):
                    page_num = idx + 1
                    if isinstance(chunk, dict):
                        page_num = chunk.get("metadata", {}).get("page_number", idx + 1)
                        text_content = chunk.get("text", "")
                    else:
                        text_content = str(chunk)

                    if text_content and text_content.strip():
                        extracted_pages.append({"page": page_num, "text": text_content.strip()})
                        total_text_length += len(text_content.strip())
        except Exception as p_err:
            print(f"pymupdf4llm layout extraction warning: {p_err}. Falling back to standard fitz...")

        # 2. Fallback to PyMuPDF fitz plain text if pymupdf4llm yielded no text
        if not extracted_pages:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            num_pages = len(doc)
            for i in range(num_pages):
                page = doc.load_page(i)
                text = page.get_text("text")
                if text:
                    clean_text = "\n".join([line.strip() for line in text.split("\n") if line.strip()])
                    if clean_text:
                        extracted_pages.append({"page": i + 1, "text": clean_text})
                        total_text_length += len(clean_text)
            doc.close()

        # 3. Fallback to OCR for scanned PDFs
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        num_pages = len(doc)
        doc.close()

        if total_text_length < (num_pages * 50) or total_text_length < 100:
            print("Scanned PDF detected (low text volume). Falling back to Groq Vision OCR...")
            
            try:
                client = get_groq_vision_client()
            except Exception:
                client = get_groq_client()
            vision_model = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
            
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            ocr_pages = []
            
            for i in range(len(doc)):
                page = doc.load_page(i)
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("jpeg")
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                
                try:
                    response = client.chat.completions.create(
                        model=vision_model,
                        max_tokens=4096,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{img_b64}"
                                        }
                                    },
                                    {
                                        "type": "text",
                                        "text": (
                                            "This is a page from a scanned PDF document. Please transcribe all the text exactly as it appears. "
                                            "Do not summarize or omit anything. Maintain the original structure where possible."
                                        )
                                    }
                                ]
                            }
                        ]
                    )
                    page_text = response.choices[0].message.content or ""
                    if page_text.strip():
                        ocr_pages.append({"page": i + 1, "text": page_text.strip()})
                except Exception as page_err:
                    print(f"OCR failed for page {i+1}: {page_err}")
                    
            doc.close()
            if ocr_pages:
                extracted_pages = ocr_pages
            print("OCR Extraction complete.")
                    
        return extracted_pages
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")


