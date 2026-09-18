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
    document_structure: Optional[Dict[str, Any]] = Field(default=None, description="Optional normalized document structure hierarchy metadata")

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
    Schema for the incoming request to the /image/explain or /explain-image endpoint.
    """
    image_id: Optional[str] = Field(default=None, description="The ID of the image to explain")
    image_base64: Optional[str] = Field(default=None, description="Optional raw base64 data of image")
    image_format: Optional[str] = Field(default="jpeg", description="Optional format of base64 image")
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


# ==========================================
# Document Structure Hierarchy Schemas
# ==========================================
class HierarchyNodeResponse(BaseModel):
    """
    Schema representing a single topic, subtopic, sub-subtopic, or section node in the document hierarchy.
    """
    node_id: str = Field(description="Unique node ID")
    title: str = Field(description="Title of the topic or section")
    level: int = Field(description="Hierarchy depth level (1=Main Topic, 2=Subtopic, 3=Sub-subtopic, 4=Section)")
    level_name: str = Field(description="Level label (Main Topic, Subtopic, Sub-subtopic, Section)")
    page_start: int = Field(description="Starting page number")
    page_end: int = Field(description="Ending page number")
    parent_id: Optional[str] = Field(default=None, description="Parent node ID")
    children: List[Dict[str, Any]] = Field(default=[], description="Nested child nodes")
    relationships: Dict[str, Any] = Field(default={}, description="Relationship metadata (parent_title, sibling_prev, sibling_next, page_span)")

class DocumentStructureResponse(BaseModel):
    """
    Schema for outgoing document structure response containing complete hierarchy tree.
    """
    success: bool
    document_name: str
    total_pages: int
    total_topics: int
    main_topics_count: int
    max_depth: int
    hierarchy_tree: List[Dict[str, Any]] = Field(default=[], description="Nested root topics tree")
    flat_nodes: List[Dict[str, Any]] = Field(default=[], description="Flat list of all hierarchy nodes")


# ==========================================
# AI Research Report Schemas
# ==========================================
class ResearchReportRequest(BaseModel):
    """
    Schema for incoming request to generate an AI Research Report based on document structure.
    """
    focus_topic: Optional[str] = Field(default=None, description="Optional specific topic to focus the research report on")
    detail_level: Optional[str] = Field(default="comprehensive", description="Detail level: executive, comprehensive, or deep-dive")

class ResearchReportResponse(BaseModel):
    """
    Schema for outgoing AI Research Report response.
    """
    success: bool
    document_name: str
    report_markdown: str = Field(description="Synthesized markdown research report structured by document topics")
    structure_overview: Dict[str, Any] = Field(default={}, description="Summary of main topics and hierarchy metadata used")



