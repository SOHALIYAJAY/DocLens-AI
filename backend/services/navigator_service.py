import os
import json
import hashlib
import fitz
import pymupdf4llm
from pydantic import ValidationError
from models.schemas import NavigatorResponse, NavigatorSection, NavigatorItem
from services.llm_service import get_groq_client, get_groq_model

CACHE_DIR = ".navigator_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def generate_navigator(file_bytes: bytes, filename: str) -> NavigatorResponse:
    """
    Orchestrates the navigator generation.
    Checks cache first, if not found, generates and caches the result.
    """
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{file_hash}.json")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return NavigatorResponse(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"Cache read error: {e}. Regenerating...")
            
    # Regenerate
    structured_data = extract_structure_pymupdf(file_bytes)
    
    # Enrich with LLM
    final_navigator = enrich_with_llm(structured_data, filename)
    
    # Save cache
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(final_navigator.json())
        
    return final_navigator

def extract_structure_pymupdf(file_bytes: bytes) -> dict:
    """
    Extracts structural information directly from PyMuPDF.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    num_pages = len(doc)
    word_count = 0
    
    sections = []
    figures = []
    tables = []
    links = []
    full_text = ""
    
    # Simple heuristic to extract headings (toc is ideal if present)
    toc = doc.get_toc()
    if toc:
        for lvl, title, page in toc:
            sections.append({
                "title": title,
                "page": page,
                "description": None
            })
            
    for i in range(num_pages):
        page = doc.load_page(i)
        
        # Word Count
        text = page.get_text("text")
        words = text.split()
        word_count += len(words)
        
        # Tables (using fitz find_tables)
        try:
            tabs = page.find_tables()
            for j, tab in enumerate(tabs.tables):
                tables.append({
                    "title": f"Table {len(tables)+1}",
                    "page": i + 1,
                    "description": "Extracted table"
                })
        except Exception:
            pass # ignore table errors
            
        # Images / Figures
        try:
            img_list = page.get_images(full=True)
            for img in img_list:
                figures.append({
                    "title": f"Figure {len(figures)+1}",
                    "page": i + 1,
                    "description": "Extracted image"
                })
        except Exception:
            pass
            
        # Extract Links
        try:
            pg_links = page.get_links()
            for lnk in pg_links:
                if "uri" in lnk and lnk["uri"]:
                    links.append({
                        "title": lnk["uri"],
                        "page": i + 1,
                        "description": "External Hyperlink"
                    })
        except Exception:
            pass
            
        # If no TOC, extract headings by font size (simplified heuristic)
        if not toc:
            try:
                blocks = page.get_text("dict").get("blocks", [])
                for b in blocks:
                    if b.get("type") == 0: # text block
                        for l in b.get("lines", []):
                            for s in l.get("spans", []):
                                if s.get("size", 0) > 12 and s.get("text", "").strip():
                                    sections.append({
                                        "title": s["text"].strip(),
                                        "page": i + 1,
                                        "description": None
                                    })
            except Exception:
                pass
                
    try:
        # Use pymupdf4llm for a vastly improved layout-aware markdown text
        full_text = pymupdf4llm.to_markdown(doc)
    except Exception as e:
        print(f"Error using pymupdf4llm: {e}")
        # Fallback to basic text if pymupdf4llm fails for some reason
        full_text = ""
        for i in range(num_pages):
            full_text += f"\n--- Page {i+1} ---\n" + doc.load_page(i).get_text("text")
            
    doc.close()
    
    # Deduplicate sections if heuristic was used
    unique_sections = []
    seen = set()
    for s in sections:
        if s["title"] not in seen and len(s["title"]) > 3:
            seen.add(s["title"])
            unique_sections.append(s)
            
    # Deduplicate links
    unique_links = []
    seen_links = set()
    for l in links:
        if l["title"] not in seen_links:
            seen_links.add(l["title"])
            unique_links.append(l)
            
    return {
        "pages": num_pages,
        "word_count": word_count,
        "sections": unique_sections,
        "figures": figures,
        "tables": tables,
        "links": unique_links,
        "full_text": full_text
    }

def enrich_with_llm(structured_data: dict, filename: str) -> NavigatorResponse:
    """
    Uses LLM to extract Chapters, Headings, Definitions, Formulas, Code Blocks, References, Diagrams, Topics, and summarize sections.
    """
    client = get_groq_client()
    model_name = get_groq_model()
    
    # We will pass a truncated version of the full text to avoid context limits if too large,
    # or chunk it. For simplicity, we take the first 80000 characters for structure detection.
    # We explicitly ask for valid JSON conforming to the schema.
    text_sample = structured_data["full_text"][:80000] 
    
    prompt = f"""
You are an expert AI document analyzer. 
I have extracted some structural information from a PDF document.
Your task is to identify and extract Chapters, Headings, Definitions, Formulas, Code Blocks, References, Diagrams, and Frequently Mentioned Topics, and provide small summaries for the sections.

Document Name: {filename}
Pages: {structured_data["pages"]}
Word Count: {structured_data["word_count"]}

Here is the document text (truncated if very large):
<text>
{text_sample}
</text>

Return the result STRICTLY as a JSON object matching this schema:
{{
  "chapters": [ {{"title": "Chapter Name", "page": 1, "description": "Chapter summary"}} ],
  "headings": [ {{"title": "Heading Name", "page": 1, "description": "Optional details"}} ],
  "definitions": [ {{"title": "Term", "page": 1, "description": "Definition summary"}} ],
  "formulas": [ {{"title": "Formula Name", "page": 1, "description": "Formula expression"}} ],
  "code_blocks": [ {{"title": "Code Block", "page": 1, "description": "Language or purpose"}} ],
  "references": [ {{"title": "Reference Name", "page": 1, "description": "Details"}} ],
  "diagrams": [ {{"title": "Diagram Name", "page": 1, "description": "Description of the diagram"}} ],
  "frequently_mentioned_topics": [ {{"title": "Topic Name", "page": 1, "description": "Why it's important"}} ],
  "section_summaries": {{ "Section Name": "Small summary string" }},
  "estimated_difficulty": "Beginner | Intermediate | Advanced"
}}

Rules:
- Do NOT include any markdown code blocks (e.g. ```json). 
- Return ONLY the raw JSON string.
- Page numbers should be integers based on "--- Page X ---" markers in the text.
"""
    
    chapters = []
    headings = []
    definitions = []
    formulas = []
    code_blocks = []
    references = []
    diagrams = []
    topics = []
    section_summaries = {}
    difficulty = "Intermediate"
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            max_tokens=2048,
            temperature=0.0,
            messages=[
                {"role": "system", "content": "You only output raw valid JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        
        final_text = response.choices[0].message.content or ""
        final_text = final_text.replace("```json", "").replace("```", "").strip()
        
        extracted = json.loads(final_text)
        chapters = extracted.get("chapters", [])
        headings = extracted.get("headings", [])
        definitions = extracted.get("definitions", [])
        formulas = extracted.get("formulas", [])
        code_blocks = extracted.get("code_blocks", [])
        references = extracted.get("references", [])
        diagrams = extracted.get("diagrams", [])
        topics = extracted.get("frequently_mentioned_topics", [])
        section_summaries = extracted.get("section_summaries", {})
        difficulty = extracted.get("estimated_difficulty", "Intermediate")
    except Exception as e:
        print(f"LLM Enrichment error: {e}")
        # fallback to empty lists if LLM fails
        
    reading_time_mins = max(1, structured_data["word_count"] // 200)
    
    # Build NavigatorResponse
    navigator_sections = []
    
    if chapters:
        navigator_sections.append(NavigatorSection(title="Chapters", items=[NavigatorItem(**c) for c in chapters]))
        
    if structured_data["sections"]:
        items = []
        for s in structured_data["sections"]:
            items.append(NavigatorItem(
                title=s["title"], 
                page=s["page"], 
                description=section_summaries.get(s["title"])
            ))
        navigator_sections.append(NavigatorSection(title="Sections", items=items))
        
    if headings:
        navigator_sections.append(NavigatorSection(title="Headings", items=[NavigatorItem(**h) for h in headings]))

    if definitions:
        navigator_sections.append(NavigatorSection(title="Definitions", items=[NavigatorItem(**d) for d in definitions]))
    if formulas:
        navigator_sections.append(NavigatorSection(title="Formulas", items=[NavigatorItem(**f) for f in formulas]))
    if structured_data["figures"]:
        navigator_sections.append(NavigatorSection(title="Figures", items=[NavigatorItem(**f) for f in structured_data["figures"]]))
    if diagrams:
        navigator_sections.append(NavigatorSection(title="Diagrams", items=[NavigatorItem(**d) for d in diagrams]))
    if structured_data["tables"]:
        navigator_sections.append(NavigatorSection(title="Tables", items=[NavigatorItem(**t) for t in structured_data["tables"]]))
    if code_blocks:
        navigator_sections.append(NavigatorSection(title="Code Blocks", items=[NavigatorItem(**c) for c in code_blocks]))
    if references:
        navigator_sections.append(NavigatorSection(title="References", items=[NavigatorItem(**r) for r in references]))
    if topics:
        navigator_sections.append(NavigatorSection(title="Frequently Mentioned Topics", items=[NavigatorItem(**t) for t in topics]))
    if structured_data.get("links"):
        navigator_sections.append(NavigatorSection(title="Document Links", items=[NavigatorItem(**l) for l in structured_data["links"]]))
        
    return NavigatorResponse(
        success=True,
        document_name=filename,
        pages=structured_data["pages"],
        word_count=structured_data["word_count"],
        estimated_reading_time=f"{reading_time_mins} mins",
        estimated_difficulty=difficulty,
        definitions_found=len(definitions),
        figures_found=len(structured_data["figures"]),
        tables_found=len(structured_data["tables"]),
        code_blocks_found=len(code_blocks),
        references_found=len(references),
        chapters_found=len(chapters),
        headings_found=len(headings),
        diagrams_found=len(diagrams),
        topics_found=len(topics),
        images_found=len(structured_data["figures"]),
        sections=navigator_sections
    )
