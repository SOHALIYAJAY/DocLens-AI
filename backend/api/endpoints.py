# api/endpoints.py
# This file defines the actual API routes (endpoints) that clients will call.

from fastapi import APIRouter, UploadFile, File, HTTPException
import os
from models.schemas import ChatRequest, ChatResponse, UploadResponse, SummaryRequest, SummaryResponse, LocalUploadRequest
from services.llm_service import generate_response, generate_summary
from services.pdf_service import extract_text_from_pdf
from services.chunk_service import chunk_text
from services.embedding_service import generate_embeddings
from services.vector_service import add_to_knowledge_base, clear_knowledge_base, get_all_chunks
from services.retriever_service import retrieve_relevant_chunks

# Create an APIRouter instance
router = APIRouter()

@router.post("/upload-pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Endpoint to upload a PDF, extract text, chunk it, embed it, and store it in FAISS.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    try:
        # 1. Read file bytes
        file_bytes = await file.read()
        
        # 2. Extract text (returns List[Dict])
        pdf_pages = extract_text_from_pdf(file_bytes)
        if not pdf_pages:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF")
            
        # 3. Chunk text (returns List[Dict])
        chunks = chunk_text(pdf_pages)
        
        # 4. Store in vector database (we clear previous KB to act as a single-document QA for now)
        # ChromaDB will automatically handle embeddings via our MiniLMEmbeddingFunction
        clear_knowledge_base()
        add_to_knowledge_base(chunks)
        
        return UploadResponse(
            success=True,
            filename=file.filename,
            num_chunks=len(chunks)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-local-pdf", response_model=UploadResponse)
async def upload_local_pdf(request: LocalUploadRequest):
    """
    Endpoint to load a local PDF directly from the filesystem (useful for file:// URLs).
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="Local file not found on backend.")
    if not request.file_path.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    try:
        # Read file bytes directly from local filesystem
        with open(request.file_path, 'rb') as f:
            file_bytes = f.read()
            
        pdf_pages = extract_text_from_pdf(file_bytes)
        if not pdf_pages:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF")
            
        chunks = chunk_text(pdf_pages)
        
        clear_knowledge_base()
        add_to_knowledge_base(chunks)
        
        return UploadResponse(
            success=True,
            filename=os.path.basename(request.file_path),
            num_chunks=len(chunks)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat", response_model=ChatResponse)
async def chat_pdf(request: ChatRequest):
    """
    Endpoint to answer questions based on the uploaded PDF using RAG.
    """
    try:
        # 1. Retrieve relevant chunks from the vector store
        relevant_chunks = retrieve_relevant_chunks(request.question)
        
        if not relevant_chunks:
            return ChatResponse(
                success=True,
                answer="I don't have any document loaded or couldn't find relevant context."
            )
            
        # 2. Generate answer using the LLM and the retrieved context
        answer = generate_response(
            context_chunks=relevant_chunks,
            question=request.question
        )
        
        return ChatResponse(
            success=True,
            answer=answer
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/summarize", response_model=SummaryResponse)
async def summarize_pdf(request: SummaryRequest):
    """
    Endpoint to summarize extracted PDF text.
    Accepts summary_type: 'minimum', 'medium', or 'large'.
    """
    # Use default 'medium' if the client explicitly passed null for summary_type
    summary_type = request.summary_type or "medium"
    
    text_to_summarize = request.pdf_text
    
    if not text_to_summarize or "via backend upload" in text_to_summarize or "Extracted" in text_to_summarize:
        chunks = get_all_chunks()
        if not chunks:
            raise HTTPException(status_code=400, detail="No PDF document is loaded for summarization.")
        text_to_summarize = "\n\n".join(chunks)
    
    # Pass the incoming data to our Gemini LLM service layer for summarization
    summary = generate_summary(
        pdf_text=text_to_summarize,
        summary_type=summary_type
    )
    
    return SummaryResponse(
        success=True,
        summary=summary
    )
