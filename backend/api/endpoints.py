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

from services.query_rewriter_service import rewrite_query
from services.table_service import table_service
from services.figure_service import figure_service
from services.topic_service import topic_service
from services.document_structure_service import document_structure_service
from services.research_report_service import research_report_service
from models.schemas import DocumentStructureResponse, ResearchReportRequest, ResearchReportResponse
from services.retriever_service import retrieve_relevant_chunks, retrieve_relevant_chunks_with_metadata
from services.citation_service import extract_sources_from_metadata, attach_sources_to_answer

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
        
        # 4. Store in vector database, BM25 index, context expansion store, table registry & figure registry
        clear_knowledge_base()
        add_to_knowledge_base(chunks)
        
        bm25_service.clear_index()
        bm25_service.add_documents(chunks)
        
        context_expansion_service.clear_chunks()
        context_expansion_service.set_document_chunks(chunks)

        table_service.clear_tables()
        table_service.extract_and_register_from_chunks(chunks)
        
        # 5. Extract images automatically & register figures
        extracted_images = extract_and_store_images(file_bytes)
        figure_service.clear_figures()
        figure_service.extract_and_register_from_chunks(chunks, extracted_images)
        
        topic_service.clear_topics()
        topic_service.extract_and_register_from_chunks(chunks, file_bytes=file_bytes, filename=file.filename)
        
        ds_manifest = None
        try:
            ds_manifest = document_structure_service.extract_structure(file_bytes=file_bytes, filename=file.filename, chunks=chunks)
        except Exception as ds_err:
            print(f"[DOCUMENT_STRUCTURE] Non-blocking extraction note: {ds_err}")

        return UploadResponse(
            success=True,
            filename=file.filename,
            num_chunks=len(chunks),
            images=extracted_images,
            document_structure=ds_manifest
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-local-pdf", response_model=UploadResponse)
async def upload_local_pdf(request: LocalUploadRequest):
    """
    Endpoint to load a local PDF directly from the filesystem (useful for file:// URLs).
    """
    clean_path = request.file_path.split('#')[0].split('?')[0].strip()
    if not os.path.exists(clean_path):
        raise HTTPException(status_code=404, detail=f"Local file not found on backend: {clean_path}")
    if not clean_path.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    try:
        # Read file bytes directly from local filesystem
        with open(clean_path, 'rb') as f:
            file_bytes = f.read()
            
        filename = os.path.basename(clean_path)
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

        table_service.clear_tables()
        table_service.extract_and_register_from_chunks(chunks)
        
        extracted_images = extract_and_store_images(file_bytes)
        figure_service.clear_figures()
        figure_service.extract_and_register_from_chunks(chunks, extracted_images)
        
        topic_service.clear_topics()
        topic_service.extract_and_register_from_chunks(chunks, file_bytes=file_bytes, filename=filename)
        
        ds_manifest = None
        try:
            ds_manifest = document_structure_service.extract_structure(file_bytes=file_bytes, filename=filename, chunks=chunks)
        except Exception as ds_err:
            print(f"[DOCUMENT_STRUCTURE] Non-blocking extraction note: {ds_err}")

        return UploadResponse(
            success=True,
            filename=filename,
            num_chunks=len(chunks),
            images=extracted_images,
            document_structure=ds_manifest
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current-document")
async def get_current_document():
    """
    Returns the metadata and name of the currently active document loaded in the knowledge base.
    """
    try:
        chunks = context_expansion_service.doc_chunks
        if not chunks:
            raw_docs = get_all_chunks()
            if not raw_docs:
                return {
                    "loaded": False,
                    "filename": "No PDF loaded",
                    "num_chunks": 0,
                    "pages": []
                }
            return {
                "loaded": True,
                "filename": "Active Document",
                "num_chunks": len(raw_docs),
                "pages": []
            }
            
        first_chunk = chunks[0]
        filename = first_chunk.get("document_name", "Active Document.pdf")
        pages = sorted(list(set(c.get("page_number", c.get("page", 1)) for c in chunks)))
        return {
            "loaded": True,
            "filename": filename,
            "num_chunks": len(chunks),
            "pages": pages,
            "total_pages": len(pages),
            "num_tables": len(table_service.get_tables()),
            "num_figures": len(figure_service.get_figures()),
            "num_topics": len(topic_service.get_topics())
        }
    except Exception as e:
        return {
            "loaded": False,
            "filename": "Error checking document",
            "error": str(e),
            "num_chunks": 0,
            "pages": []
        }


@router.post("/clear-document")
async def clear_document_endpoint():
    """
    Clears all active document chunks, vector store, and BM25 indices to start fresh.
    """
    try:
        clear_knowledge_base()
        bm25_service.clear_index()
        context_expansion_service.clear_chunks()
        table_service.clear_tables()
        figure_service.clear_figures()
        topic_service.clear_topics()
        document_structure_service.clear()
        return {
            "success": True,
            "message": "Knowledge base and document indices successfully cleared."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





@router.post("/chat", response_model=ChatResponse)
async def chat_pdf(request: ChatRequest):
    """
    Endpoint to answer questions based on the uploaded PDF using Query Understanding, Table-Aware RAG, Visual RAG, and Hybrid RAG.
    """
    try:
        if not request.question or not request.question.strip():
            return ChatResponse(
                success=True,
                answer="Sorry, we not found answer in this time."
            )

        # 1. Query Understanding & Conversational Rewriting -> Standalone Retrieval Query
        retrieval_query = rewrite_query(request.question, request.history)

        # 2. Query Classification & Intent Detection
        topic_intent = topic_service.classify_topic_intent(retrieval_query)
        table_intent = table_service.classify_query_intent(retrieval_query)
        visual_intent = figure_service.classify_visual_query(retrieval_query)

        context_chunks = []
        raw_metadata_list = []

        # 2.5 Topic & Document Structure Awareness Retrieval
        if topic_intent["is_topic_query"] and (topic_service.get_topics() or context_expansion_service.doc_chunks):
            topic_block, topic_meta = topic_service.retrieve_topic_context(retrieval_query, topic_intent)
            context_chunks.append(topic_block)
            raw_metadata_list.extend(topic_meta)

            # If user asked for specific topic details (e.g. 'topic 2'), also augment with hybrid chunks
            if topic_intent.get("query_type") == "detail":
                hybrid_text, text_meta = retrieve_relevant_chunks_with_metadata(retrieval_query, top_k=2)
                context_chunks.extend(hybrid_text)
                raw_metadata_list.extend(text_meta)

        # 3. Table-Aware Retrieval & Deterministic Calculation (when appropriate)
        elif table_intent["is_table_query"] and table_service.get_tables():
            matching_table = table_service.table_aware_retrieval(retrieval_query)
            if matching_table:
                calc_result = table_service.calculate_table_metrics(
                    matching_table, table_intent["calc_type"], retrieval_query
                )
                formatted_table_block = table_service.format_table_context(matching_table, calc_result)
                context_chunks.append(formatted_table_block)
                raw_metadata_list.append({
                    "type": "table",
                    "table_id": matching_table["table_id"],
                    "page_number": matching_table["page_number"]
                })

                hybrid_text, text_meta = retrieve_relevant_chunks_with_metadata(retrieval_query, top_k=2)
                context_chunks.extend(hybrid_text)
                raw_metadata_list.extend(text_meta)

        # 4. Figure, Diagram, Chart & Image Retrieval (when appropriate and no table matched)
        elif visual_intent["is_visual_query"] and figure_service.get_figures():
            matching_fig = figure_service.identify_relevant_figure(
                retrieval_query, target_num=visual_intent["target_num"]
            )
            if matching_fig:
                visual_evidence = None
                if visual_intent["requires_vision_ai"] and matching_fig.get("image_id"):
                    visual_evidence = figure_service.analyze_visual_evidence(matching_fig, retrieval_query)

                formatted_fig_block = figure_service.format_figure_context(matching_fig, visual_evidence)
                context_chunks.append(formatted_fig_block)
                raw_metadata_list.append({
                    "type": "figure",
                    "figure_id": matching_fig["figure_id"],
                    "page_number": matching_fig["page_number"]
                })

                hybrid_text, text_meta = retrieve_relevant_chunks_with_metadata(retrieval_query, top_k=2)
                context_chunks.extend(hybrid_text)
                raw_metadata_list.extend(text_meta)

        # 5. Fallback / Normal Hybrid Search when not table/visual related or nothing found
        if not context_chunks:
            context_chunks, text_meta = retrieve_relevant_chunks_with_metadata(retrieval_query)
            raw_metadata_list.extend(text_meta)
        
        if not context_chunks:
            if not get_all_chunks() and not context_expansion_service.doc_chunks:
                return ChatResponse(
                    success=True,
                    answer="No PDF document is currently loaded in the chatbot. Please upload a PDF file using the 'Upload PDF File' button or click 'Extract from Tab' to begin!",
                    sources=[]
                )
            return ChatResponse(
                success=True,
                answer="I couldn't find enough information in the uploaded PDF to answer that reliably.",
                sources=[]
            )
            
        # 6. Generate answer using LLM with retrieved context & capped history
        answer = generate_response(
            context_chunks=context_chunks,
            question=request.question,
            history=request.history
        )
        
        # 7. Extract deterministic sources from chunk metadata & attach to response
        structured_sources = extract_sources_from_metadata(raw_metadata_list or context_chunks)
        final_answer = attach_sources_to_answer(answer, structured_sources)

        return ChatResponse(
            success=True,
            answer=final_answer or "I couldn't find enough information in the uploaded PDF to answer that reliably.",
            sources=structured_sources
        )
    except Exception as e:
        print(f"[Chat Endpoint Warning]: {str(e)}")
        traceback.print_exc()
        return ChatResponse(
            success=False,
            answer=f"Chat processing error: {str(e)}",
            sources=[]
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


# ==========================================
# Document Structure Hierarchy Endpoints
# ==========================================
@router.post("/document-structure", response_model=DocumentStructureResponse)
async def get_document_structure_endpoint(file: UploadFile = File(...)):
    """
    Endpoint to extract explicit document structure hierarchy (Main Topics, Subtopics, Sub-subtopics, Sections, Relationships).
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        file_bytes = await file.read()
        structure = document_structure_service.extract_structure(file_bytes, file.filename)
        return DocumentStructureResponse(**structure)
    except Exception as e:
        err_msg = traceback.format_exc()
        print(err_msg)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/local-document-structure", response_model=DocumentStructureResponse)
async def get_local_document_structure_endpoint(request: LocalUploadRequest):
    """
    Endpoint to extract document structure hierarchy directly from a local PDF path.
    """
    clean_path = request.file_path.split('#')[0].split('?')[0].strip()
    if not os.path.exists(clean_path):
        raise HTTPException(status_code=404, detail=f"Local file not found: {clean_path}")
    if not clean_path.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        with open(clean_path, 'rb') as f:
            file_bytes = f.read()
        filename = os.path.basename(clean_path)
        structure = document_structure_service.extract_structure(file_bytes, filename)
        return DocumentStructureResponse(**structure)
    except Exception as e:
        err_msg = traceback.format_exc()
        print(err_msg)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/document-structure/current", response_model=DocumentStructureResponse)
async def get_current_document_structure_endpoint():
    """
    Returns the document structure hierarchy of the currently active document loaded in memory.
    """
    structure = document_structure_service.get_current_structure()
    if not structure:
        raise HTTPException(status_code=404, detail="No active document structure found in memory.")
    return DocumentStructureResponse(**structure)


# ==========================================
# AI Research Report Endpoints
# ==========================================
@router.post("/generate-research-report", response_model=ResearchReportResponse)
async def generate_research_report_endpoint(request: Optional[ResearchReportRequest] = None):
    """
    Endpoint to synthesize an AI Research Report based on the active document structure hierarchy.
    """
    try:
        focus = request.focus_topic if request else None
        detail = request.detail_level if request else "comprehensive"
        report_data = research_report_service.generate_report(focus_topic=focus, detail_level=detail)
        return ResearchReportResponse(**report_data)
    except Exception as e:
        err_msg = traceback.format_exc()
        print(err_msg)
        raise HTTPException(status_code=500, detail=str(e))


