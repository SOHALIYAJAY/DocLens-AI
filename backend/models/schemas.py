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
    images: list[dict] = Field(default=[], description="List of extracted images with metadata (image_id, page, format)")

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

# ==========================================
# Image Explanation Schemas
# ==========================================
class ImageExplanationResponse(BaseModel):
    """
    Schema for the outgoing response from the /image/explain endpoint.
    """
    success: bool
    title: str = Field(description="A concise title for the image")
    summary: str = Field(description="A short summary of what the image represents")
    explanation: str = Field(description="A detailed explanation of the image contents")
    important_components: list[str] = Field(description="Important components or objects identified")
    relationships: list[str] = Field(description="Relationships between components or flows")
    key_takeaways: list[str] = Field(description="Key takeaways from the image")
    real_world_application: str = Field(description="Real-world application of the concept")

class ExplainImageRequest(BaseModel):
    """
    Schema for the incoming request to the /explain-image endpoint.
    """
    image_id: str = Field(description="The ID of the image to explain")
    prompt: Optional[str] = Field(default=None, description="Optional prompt to guide the explanation")

# ==========================================
# Navigator Schemas
# ==========================================
class NavigatorItem(BaseModel):
    """
    A single item in the navigator (e.g., a definition, a figure, a section).
    """
    title: str = Field(description="Title or name of the item")
    page: int = Field(description="The page number where this item is located")
    description: Optional[str] = Field(default=None, description="Optional short summary or content snippet")

class NavigatorSection(BaseModel):
    """
    A group of items (e.g., all formulas, all definitions).
    """
    title: str = Field(description="Section title (e.g., 'Formulas', 'Definitions')")
    summary: Optional[str] = Field(default=None, description="Optional small AI summary for chapters/sections")
    items: list[NavigatorItem] = Field(default=[], description="List of items in this section")

class NavigatorResponse(BaseModel):
    """
    The full navigator response containing document overview and all extracted sections.
    """
    success: bool
    document_name: str
    pages: int
    word_count: int
    estimated_reading_time: str
    estimated_difficulty: str
    definitions_found: int
    formulas_found: int = 0
    figures_found: int
    tables_found: int
    code_blocks_found: int
    references_found: int
    chapters_found: int = 0
    headings_found: int = 0
    diagrams_found: int = 0
    topics_found: int = 0
    images_found: int = 0
    
    sections: list[NavigatorSection] = Field(default=[], description="Collapsible sections (Chapters, Definitions, etc.)")

