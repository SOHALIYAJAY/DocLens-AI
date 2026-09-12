# api/endpoints.py
# This file defines the actual API routes (endpoints) that clients will call.

import base64
from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import traceback
from models.schemas import ChatRequest, ChatResponse, UploadResponse, SummaryRequest, SummaryResponse, LocalUploadRequest, ExplainImageRequest
from services.llm_service import generate_response, generate_summary
from services.pdf_service import extract_text_from_pdf, generate_document_id
from services.image_service import extract_and_store_images, get_image_base64
from services.vision_service import analyze_image
from services.chunk_service import chunk_text, chunk_pages_with_metadata
from services.embedding_service import generate_embeddings
from services.vector_service import add_to_knowledge_base, clear_knowledge_base, get_all_chunks
from services.bm25_service import bm25_service
from services.context_expansion_service import context_expansion_service
from services.retriever_service import retrieve_relevant_chunks
from services.navigator_service import generate_navigator
from models.schemas import NavigatorResponse
from services.pdf_generator_service import create_navigator_pdf

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
            
        # 3. Chunk text with document & page metadata
        doc_id = generate_document_id(file_bytes, file.filename)
        chunks = chunk_pages_with_metadata(pdf_pages, document_id=doc_id, document_name=file.filename)
        
        # 4. Store in vector database, BM25 index & context expansion store
        clear_knowledge_base()
        add_to_knowledge_base(chunks)
        
        bm25_service.clear_index()
        bm25_service.add_documents(chunks)
        
        context_expansion_service.clear_chunks()
        context_expansion_service.set_document_chunks(chunks)
        
        # 5. Extract images automatically
        extracted_images = extract_and_store_images(file_bytes)
        
        return UploadResponse(
            success=True,
            filename=file.filename,
            num_chunks=len(chunks),
            images=extracted_images
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-local-pdf", response_model=UploadResponse)
async def upload_local_pdf(request: LocalUploadRequest):
    """
    Endpoint to load a local PDF directly from the filesystem (useful for file:// URLs).
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail=f"Local file not found on backend: {request.file_path}")
    if not request.file_path.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    try:
        # Read file bytes directly from local filesystem
        with open(request.file_path, 'rb') as f:
            file_bytes = f.read()
            
        filename = os.path.basename(request.file_path)
        pdf_pages = extract_text_from_pdf(file_bytes)
        if not pdf_pages:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF")
            
        doc_id = generate_document_id(file_bytes, filename)
        chunks = chunk_pages_with_metadata(pdf_pages, document_id=doc_id, document_name=filename)
        
        clear_knowledge_base()
        add_to_knowledge_base(chunks)
        
        bm25_service.clear_index()
        bm25_service.add_documents(chunks)
        
        context_expansion_service.clear_chunks()
        context_expansion_service.set_document_chunks(chunks)
        
        extracted_images = extract_and_store_images(file_bytes)
        
        return UploadResponse(
            success=True,
            filename=filename,
            num_chunks=len(chunks),
            images=extracted_images
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/chat", response_model=ChatResponse)
async def chat_pdf(request: ChatRequest):
    """
    Endpoint to answer questions based on the uploaded PDF using RAG.
    """
    try:
        if not request.question or not request.question.strip():
            return ChatResponse(
                success=True,
                answer="Sorry, we not found answer in this time."
            )

        # 1. Retrieve relevant chunks from the vector store
        relevant_chunks = retrieve_relevant_chunks(request.question)
        
        if not relevant_chunks:
            return ChatResponse(
                success=True,
                answer="Sorry, we not found answer in this time."
            )
            
        # 2. Generate answer using the LLM and the retrieved context
        answer = generate_response(
            context_chunks=relevant_chunks,
            question=request.question
        )
        
        return ChatResponse(
            success=True,
            answer=answer or "Sorry, we not found answer in this time."
        )
    except Exception as e:
        print(f"[Chat Endpoint Warning]: {str(e)}")
        return ChatResponse(
            success=True,
            answer="Sorry, we not found answer in this time."
        )

@router.post("/explain-image")
async def explain_image_endpoint(request: ExplainImageRequest):
    """
    Endpoint to analyze and explain an extracted PDF image using Vision AI.
    """
    try:
        img_data = get_image_base64(request.image_id)
        if not img_data:
            raise HTTPException(status_code=404, detail="Image session expired or not found. Please re-extract PDF.")

        explanation = analyze_image(
            image_base64=img_data["base64_data"],
            image_format=img_data["format"],
            prompt=request.prompt
        )

        return {
            "success": True,
            "data": explanation
        }
    except Exception as e:
        print(f"[Explain Image Error]: {str(e)}")
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

@router.post("/generate-navigator", response_model=NavigatorResponse)
async def create_navigator(file: UploadFile = File(...)):
    """
    Endpoint to generate or retrieve the cached AI Document Navigator for a PDF.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    try:
        # Read file bytes
        file_bytes = await file.read()
        
        # Call navigator service which handles caching internally
        navigator_res = generate_navigator(file_bytes, file.filename)
        
        # Extract links dynamically from the bytes (handles cached PDFs too!)
        try:
            from services.pdf_generator_service import extract_links_from_pdf_bytes
            links = extract_links_from_pdf_bytes(file_bytes)
            if links:
                from models.schemas import NavigatorSection, NavigatorItem
                # Check if "Document Links" section is already in navigator_res.sections
                has_links = any(s.title == "Document Links" for s in navigator_res.sections)
                if not has_links:
                    navigator_res.sections.append(NavigatorSection(
                        title="Document Links",
                        items=[NavigatorItem(**l) for l in links]
                    ))
        except Exception as e:
            print(f"Error appending links dynamically: {e}")
            
        return navigator_res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-local-navigator", response_model=NavigatorResponse)
async def create_local_navigator(request: LocalUploadRequest):
    """
    Endpoint to generate or retrieve the cached AI Document Navigator for a local PDF.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail=f"Local file not found on backend: {request.file_path}")
    if not request.file_path.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    try:
        # Read file bytes directly from local filesystem
        with open(request.file_path, 'rb') as f:
            file_bytes = f.read()
            
        filename = os.path.basename(request.file_path)
        
        # Call navigator service which handles caching internally
        navigator_res = generate_navigator(file_bytes, filename)
        
        # Extract links dynamically from the bytes (handles cached PDFs too!)
        try:
            from services.pdf_generator_service import extract_links_from_pdf_bytes
            links = extract_links_from_pdf_bytes(file_bytes)
            if links:
                from models.schemas import NavigatorSection, NavigatorItem
                # Check if "Document Links" section is already in navigator_res.sections
                has_links = any(s.title == "Document Links" for s in navigator_res.sections)
                if not has_links:
                    navigator_res.sections.append(NavigatorSection(
                        title="Document Links",
                        items=[NavigatorItem(**l) for l in links]
                    ))
        except Exception as e:
            print(f"Error appending links dynamically: {e}")
            
        return navigator_res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/download-navigator-pdf")
async def download_navigator_pdf(file: UploadFile = File(...)):
    """
    Endpoint to generate or retrieve the cached AI Document Navigator and return it as a PDF.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    try:
        file_bytes = await file.read()
        navigator_res = generate_navigator(file_bytes, file.filename)
        
        # Extract links dynamically from the bytes (handles cached PDFs too!)
        try:
            from services.pdf_generator_service import extract_links_from_pdf_bytes
            links = extract_links_from_pdf_bytes(file_bytes)
            if links:
                from models.schemas import NavigatorSection, NavigatorItem
                # Check if "Document Links" section is already in navigator_res.sections
                has_links = any(s.title == "Document Links" for s in navigator_res.sections)
                if not has_links:
                    navigator_res.sections.append(NavigatorSection(
                        title="Document Links",
                        items=[NavigatorItem(**l) for l in links]
                    ))
        except Exception as e:
            print(f"Error appending links dynamically: {e}")
            
        pdf_bytes = create_navigator_pdf(navigator_res)
        
        return {
            "success": True, 
            "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8")
        }
    except Exception as e:
        err_msg = traceback.format_exc()
        print(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)

@router.post("/download-local-navigator-pdf")
async def download_local_navigator_pdf(request: LocalUploadRequest):
    """
    Endpoint to generate or retrieve the cached AI Document Navigator for a local PDF and return it as a PDF.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail=f"Local file not found on backend: {request.file_path}")
    if not request.file_path.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    try:
        with open(request.file_path, 'rb') as f:
            file_bytes = f.read()
            
        filename = os.path.basename(request.file_path)
        navigator_res = generate_navigator(file_bytes, filename)
        
        # Extract links dynamically from the bytes (handles cached PDFs too!)
        try:
            from services.pdf_generator_service import extract_links_from_pdf_bytes
            links = extract_links_from_pdf_bytes(file_bytes)
            if links:
                from models.schemas import NavigatorSection, NavigatorItem
                # Check if "Document Links" section is already in navigator_res.sections
                has_links = any(s.title == "Document Links" for s in navigator_res.sections)
                if not has_links:
                    navigator_res.sections.append(NavigatorSection(
                        title="Document Links",
                        items=[NavigatorItem(**l) for l in links]
                    ))
        except Exception as e:
            print(f"Error appending links dynamically: {e}")
            
        pdf_bytes = create_navigator_pdf(navigator_res)
        
        return {
            "success": True, 
            "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8")
        }
    except Exception as e:
        err_msg = traceback.format_exc()
        print(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)
