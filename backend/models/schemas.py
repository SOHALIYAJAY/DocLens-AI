# models/schemas.py
# This file defines the Pydantic models (schemas) used to validate 
# incoming requests and structure outgoing responses.

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List

# ==========================================
# Hybrid RAG Chunk Metadata Schema
# ==========================================
class ChunkMetadata(BaseModel):
    """
    Schema for document chunk metadata stored alongside vector embeddings in ChromaDB.
    """
    document_id: str = Field(description="Unique identifier for the PDF document")
    document_name: str = Field(description="Filename of the uploaded PDF")
    page_number: int = Field(default=1, description="Primary page number")
    page_start: int = Field(default=1, description="Starting page of chunk")
    page_end: int = Field(default=1, description="Ending page of chunk")
    section: str = Field(default="", description="Active section title")
    heading: str = Field(default="", description="Immediate heading title")
    chapter: str = Field(default="", description="Chapter title if available")
    subsection: str = Field(default="", description="Sub-heading title if available")
    parent_section: str = Field(default="", description="Parent section title")
    chunk_id: str = Field(description="Deterministic chunk ID (doc_id + page + index)")
    parent_chunk_id: str = Field(default="", description="Parent chunk ID when applicable")
    content_type: str = Field(default="text", description="Type: text, table, figure, image, code, or other")
    figure_id: str = Field(default="", description="Figure ID if chunk is a figure/diagram")
    table_id: str = Field(default="", description="Table ID if chunk is a table")
    caption: str = Field(default="", description="Caption associated with figure/table")
    source_type: str = Field(default="pdf", description="Source document type")




# ==========================================
# Chat (RAG) Schemas
# ==========================================
class ChatRequest(BaseModel):
    """
    Schema for the incoming request to the /chat endpoint.
    Expects user question and optional recent conversation history.
    """
    question: str
    history: Optional[list[dict[str, str]]] = Field(default=[], description="Recent conversation history")

class ChatResponse(BaseModel):
    """
    Schema for the outgoing response from the /chat endpoint.
    """
    success: bool
    answer: str
    sources: Optional[list[dict[str, Any]]] = Field(default=[], description="Structured source citations extracted deterministically from chunk metadata")

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
    pdf_text: Optional[str] = Field(
        default=None,
        description="Optional extracted text. If omitted, vector store chunks are used."
    )
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

