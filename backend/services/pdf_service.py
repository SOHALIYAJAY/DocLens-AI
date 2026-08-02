# services/pdf_service.py
import io
import os
import tempfile
import time
from google import genai
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
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
            print("Scanned PDF detected (low text volume). Falling back to Gemini OCR...")
            
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY is missing. Cannot perform OCR.")
                
            client = genai.Client(api_key=api_key)
            
            # Save bytes to a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(file_bytes)
                tmp_file_path = tmp_file.name
                
            try:
                # Upload file to Gemini
                print("Uploading PDF to Gemini...")
                uploaded_file = client.files.upload(file=tmp_file_path)
                
                # Wait briefly for file to be processed if needed
                while getattr(uploaded_file, "state", None) and getattr(uploaded_file.state, "name", "") == "PROCESSING":
                    print("Waiting for file processing...")
                    time.sleep(2)
                    uploaded_file = client.files.get(name=uploaded_file.name)
                
                # Ask Gemini to extract text
                print("Extracting text via Gemini...")
                prompt = (
                    "This is a scanned PDF document. Please transcribe all the text exactly as it appears. "
                    "Do not summarize or omit anything. Maintain the original structure where possible."
                )
                
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=[uploaded_file, prompt]
                )
                
                extracted_text = response.text.strip()
                extracted_pages = [{"page": 1, "text": extracted_text}]  # Gemini OCR returns a single block currently
                
                # Clean up file on Google servers
                try:
                    client.files.delete(name=uploaded_file.name)
                except Exception as del_err:
                    print(f"Warning: could not delete file from Gemini servers: {del_err}")
                print("OCR Extraction complete.")
                
            finally:
                # Always clean up local temp file
                if os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)
                    
        return extracted_pages
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")

