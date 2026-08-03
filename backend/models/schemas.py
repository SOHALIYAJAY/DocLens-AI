# models/schemas.py
# This file defines the Pydantic models (schemas) used to validate 
# incoming requests and structure outgoing responses.

from pydantic import BaseModel, Field
from typing import Optional

# ==========================================
# Chat (RAG) Schemas
# ==========================================
class ChatRequest(BaseModel):
    """
    Schema for the incoming request to the /chat endpoint.
    It only expects the user's question, as the PDF text is in the vector store.
    """
    question: str

class ChatResponse(BaseModel):
    """
    Schema for the outgoing response from the /chat endpoint.
    """
    success: bool
    answer: str

class LocalUploadRequest(BaseModel):
    """
    Schema for the incoming request to load a local PDF directly from disk.
    """
    file_path: str

class UploadResponse(BaseModel):
    """
    Schema for the outgoing response from the /upload-pdf endpoint.
    """
    success: bool
    filename: str
    num_chunks: int

# ==========================================
# Summarization Schemas
# ==========================================
class SummaryRequest(BaseModel):
    """
    Schema for the incoming request to the /summarize endpoint.
    It expects the text extracted from the PDF and the desired summary type.
    """
    pdf_text: str
    summary_type: Optional[str] = Field(
        default="medium", 
        description="The length and detail level of the summary (small, medium, large)"
    )
    

class SummaryResponse(BaseModel):
    """
    Schema for the outgoing response from the /summarize endpoint.
    It returns a success boolean and the generated summary.
    """
    success: bool
    summary: str
