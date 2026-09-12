import re
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter

def detect_content_type(text: str) -> tuple:
    """
    Detects content_type ('text', 'table', 'code', 'figure', 'image')
    and extracts table_id, figure_id, or caption if present.
    """
    # Check table
    if "|---" in text or re.search(r"\|.*\|.*\|", text):
        caption = ""
        cap_match = re.search(r"(?:Table|TABLE)\s*\d+[:\.-]?\s*([^\n]+)", text)
        if cap_match:
            caption = cap_match.group(0).strip()
        return "table", "", "table_auto", caption
        
    # Check code
    if text.strip().startswith("```") or "\n```" in text:
        return "code", "", "", ""

    # Check figure / image
    if "![" in text or re.search(r"(?:Figure|Fig\.|Diagram)\s*\d+", text, re.IGNORECASE):
        caption = ""
        fig_match = re.search(r"(?:Figure|Fig\.|Diagram)\s*\d+[:\.-]?\s*([^\n]+)", text, re.IGNORECASE)
        if fig_match:
            caption = fig_match.group(0).strip()
        return "figure", "figure_auto", "", caption

    return "text", "", "", ""

def chunk_pages_with_metadata(
    pages: List[Dict[str, Any]],
    document_id: str = "doc_default",
    document_name: str = "document.pdf",
    chunk_size: int = 1000,
    overlap: int = 200
) -> List[Dict[str, Any]]:
    """
    Splits page texts into structure-aware chunks while tracking active headings,
    page boundaries, content types, and assigning deterministic metadata.
    """
    if not pages:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        separators=[
            "\n\n# ", "\n\n## ", "\n\n### ",
            "\n\n",
            "\n",
            ". ", "? ", "! ",
            " ", ""
        ],
        is_separator_regex=False,
    )

    chunks = []
    current_chapter = ""
    current_section = ""
    current_subsection = ""
    current_parent_section = ""
    table_counter = 0
    figure_counter = 0
    total_chunk_index = 0

    for page_data in pages:
        page_num = page_data.get("page", 1)
        raw_text = page_data.get("text", "")
        
        if not raw_text.strip():
            continue

        # Inspect lines to update section tracking state
        lines = raw_text.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                current_chapter = stripped[2:].strip()
                current_section = current_chapter
                current_parent_section = ""
                current_subsection = ""
            elif stripped.startswith("## "):
                current_section = stripped[3:].strip()
                current_parent_section = current_chapter or current_section
                current_subsection = ""
            elif stripped.startswith("### "):
                current_subsection = stripped[4:].strip()
                current_parent_section = current_section or current_chapter

        # Split text of current page
        page_splits = text_splitter.split_text(raw_text)

        for c_text in page_splits:
            if not c_text.strip():
                continue

            content_type, fig_id, tbl_id, caption = detect_content_type(c_text)
            
            if content_type == "table":
                table_counter += 1
                tbl_id = f"table_{table_counter}"
            elif content_type in ("figure", "image"):
                figure_counter += 1
                fig_id = f"figure_{figure_counter}"

            total_chunk_index += 1
            chunk_id = f"{document_id}_p{page_num}_c{total_chunk_index:03d}"
            immediate_heading = current_subsection or current_section or current_chapter or ""

            chunk_meta = {
                "document_id": document_id,
                "document_name": document_name,
                "page_number": int(page_num),
                "page_start": int(page_num),
                "page_end": int(page_num),
                "section": current_section or "General",
                "heading": immediate_heading,
                "chapter": current_chapter,
                "subsection": current_subsection,
                "parent_section": current_parent_section,
                "chunk_id": chunk_id,
                "parent_chunk_id": f"{document_id}_sec_{current_section}" if current_section else "",
                "content_type": content_type,
                "figure_id": fig_id,
                "table_id": tbl_id,
                "caption": caption,
                "source_type": "pdf",
                "page": int(page_num),  # Preserved for backward compatibility
                "text": c_text
            }

            chunks.append(chunk_meta)

            print(f"[CHUNK] ID: {chunk_id} | Pages: {page_num}-{page_num} | Section: {current_section or 'General'} | Type: {content_type}")

    print(f"[INGESTION] Document: {document_name} | ID: {document_id} | Pages: {len(pages)} | Chunks: {len(chunks)}")
    return chunks

def chunk_text(pages: List[Dict[str, Any]], chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
    """
    Backward-compatible wrapper for chunk_pages_with_metadata.
    """
    return chunk_pages_with_metadata(
        pages=pages,
        document_id="doc_default",
        document_name="document.pdf",
        chunk_size=chunk_size,
        overlap=overlap
    )


def chunk_text_by_tokens(
    text: str, 
    max_tokens_per_chunk: int = 6500, 
    overlap_tokens: int = 400
) -> List[str]:
    """
    Splits document text into chunks targeting ~6,000-7,000 tokens per chunk
    with ~300-500 tokens of overlap, preserving paragraph/sentence boundaries
    and original document sequence.
    """
    if not text or not text.strip():
        return []
        
    from services.token_service import count_tokens

    if count_tokens(text) <= max_tokens_per_chunk:
        return [text]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_tokens_per_chunk,
        chunk_overlap=overlap_tokens,
        length_function=count_tokens,
        separators=[
            "\n\n# ", "\n\n## ", "\n\n### ",
            "\n\n1. ", "\n\n2. ", "\n\n3. ", "\n\n4. ", "\n\n5. ", "\n\n6. ", "\n\n7. ", "\n\n8. ",
            "\n\nABSTRACT", "\n\nINTRODUCTION", "\n\nMETHODOLOGY", "\n\nMETHODS", "\n\nRESULTS", "\n\nDISCUSSION", "\n\nCONCLUSION", "\n\nLIMITATIONS",
            "\n\n",
            "\n",
            ". ", "? ", "! ",
            " ", ""
        ],
        is_separator_regex=False,
    )

    return splitter.split_text(text)


