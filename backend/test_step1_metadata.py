# test_step1_metadata.py
import os
import sys
import unittest

from services.pdf_service import extract_text_from_pdf, generate_document_id
from services.chunk_service import chunk_pages_with_metadata
from services.vector_service import add_to_knowledge_base, clear_knowledge_base, search_knowledge_base, get_all_chunks
from services.retriever_service import retrieve_relevant_chunks
from services.llm_service import generate_response

def run_step1_tests():
    print("\n========== RUNNING STEP 1 METADATA VERIFICATION TESTS ==========")
    
    # 1. Check test PDF existence
    test_pdf_path = os.path.join(os.path.dirname(__file__), "test.pdf")
    if not os.path.exists(test_pdf_path):
        print(f"ERROR: {test_pdf_path} not found.")
        sys.exit(1)
        
    with open(test_pdf_path, "rb") as f:
        pdf_bytes = f.read()
        
    # 2. Test document ID generation
    doc_id = generate_document_id(pdf_bytes, "test.pdf")
    print(f"Generated Document ID: {doc_id}")
    assert doc_id.startswith("doc_"), "Document ID must start with doc_"
    
    # 3. Test text extraction
    pages = extract_text_from_pdf(pdf_bytes)
    print(f"Extracted {len(pages)} pages.")
    assert len(pages) > 0, "Pages should not be empty"
    assert "page" in pages[0] and "text" in pages[0], "Page dict missing page or text"
    
    # 4. Test chunking with metadata
    chunks = chunk_pages_with_metadata(pages, document_id=doc_id, document_name="test.pdf")
    print(f"Generated {len(chunks)} metadata-enriched chunks.")
    assert len(chunks) > 0, "Chunks list should not be empty"
    
    sample_chunk = chunks[0]
    required_keys = [
        "document_id", "document_name", "page_number", "page_start", "page_end",
        "section", "heading", "chapter", "subsection", "parent_section",
        "chunk_id", "content_type", "figure_id", "table_id", "caption", "source_type", "text"
    ]
    for key in required_keys:
        assert key in sample_chunk, f"Chunk missing metadata key: {key}"
        
    print(f"Sample Chunk ID: {sample_chunk['chunk_id']}")
    print(f"Sample Chunk Metadata: {sample_chunk}")
    
    # 5. Test vector store ingestion & retrieval
    clear_knowledge_base()
    add_to_knowledge_base(chunks)
    
    retrieved = search_knowledge_base("layout test page", top_k=2)
    print(f"Retrieved {len(retrieved)} items from search_knowledge_base.")
    assert len(retrieved) > 0, "Retrieved list should not be empty"
    
    meta = retrieved[0].get("metadata", {})
    print(f"Retrieved metadata from ChromaDB: {meta}")
    assert meta.get("document_id") == doc_id, f"Document ID mismatch: {meta.get('document_id')} vs {doc_id}"
    assert meta.get("chunk_id") == sample_chunk["chunk_id"] or "chunk_id" in meta, "Chunk ID missing in ChromaDB metadata"
    
    # 6. Test retriever_service compatibility
    retrieved_formatted = retrieve_relevant_chunks("layout test page")
    print(f"Retriever Service returned {len(retrieved_formatted)} formatted chunks.")
    assert len(retrieved_formatted) > 0, "Retriever Service formatted chunks empty"
    
    # 7. Test get_all_chunks for summarization fallback
    all_c = get_all_chunks()
    print(f"get_all_chunks returned {len(all_c)} text items.")
    assert len(all_c) > 0, "get_all_chunks empty"
    
    print("\n========== ALL STEP 1 METADATA TESTS PASSED SUCCESSFULLY! ==========\n")

if __name__ == "__main__":
    run_step1_tests()
