# services/citation_service.py
"""
Citation Service for DocLens-AI Chatbot.
Extracts exact, deterministic PDF sources (page numbers, table IDs, figure IDs) directly from stored chunk metadata.
Prohibits LLM page number inventions.
"""

import re
from typing import List, Dict, Any, Optional

def clean_identifier(raw_id: str, prefix: str) -> str:
    """
    Cleans raw IDs like 'table_2' -> '2' or 'figure_4' -> '4' for neat formatting,
    while leaving non-numeric IDs like 'arch_diag' as 'arch_diag'.
    """
    if not raw_id:
        return ""
    clean = str(raw_id).strip()
    if clean.lower().startswith(prefix.lower()):
        suffix = clean[len(prefix):].strip("_").strip("-").strip()
        if suffix:
            return suffix
    return clean

def extract_sources_from_metadata(metadata_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts unique structured sources from chunk metadata dictionaries, table objects, or figure objects.
    
    Args:
        metadata_list (List[Dict[str, Any]]): List of metadata dicts or text chunks.
        
    Returns:
        List[Dict[str, Any]]: List of unique source objects with display_string and metadata.
    """
    if not metadata_list:
        return []

    sources = []
    seen_keys = set()

    for item in metadata_list:
        if not isinstance(item, dict):
            # Parse text string if passed
            txt = str(item)
            page_match = re.search(r"\[Pages?\s*(\d+)(?:-(\d+))?\]", txt, re.IGNORECASE)
            tbl_match = re.search(r"\[Table\s*(?:ID:)?\s*([^\]\s]+)\]", txt, re.IGNORECASE)
            fig_match = re.search(r"\[Figure\s*([^\]\s]+)\]", txt, re.IGNORECASE)

            pg = int(page_match.group(1)) if page_match else 1
            tbl_id = tbl_match.group(1) if tbl_match else ""
            fig_id = fig_match.group(1) if fig_match else ""

            item = {
                "page_number": pg,
                "table_id": tbl_id,
                "figure_id": fig_id
            }

        pg_num = int(item.get("page_number", item.get("page", item.get("page_start", 1))))
        pg_end = int(item.get("page_end", pg_num))
        table_id = item.get("table_id", "")
        figure_id = item.get("figure_id", "")

        # 1. Table Source
        if table_id:
            cleaned_tbl = clean_identifier(table_id, "table")
            disp_str = f"Table {cleaned_tbl} — Page {pg_num}"
            key = ("table", table_id, pg_num)
            if key not in seen_keys:
                seen_keys.add(key)
                sources.append({
                    "type": "table",
                    "table_id": table_id,
                    "page_number": pg_num,
                    "display_string": disp_str
                })
            continue

        # 2. Figure / Diagram / Image Source
        if figure_id:
            cleaned_fig = clean_identifier(figure_id, "figure")
            disp_str = f"Figure {cleaned_fig} — Page {pg_num}"
            key = ("figure", figure_id, pg_num)
            if key not in seen_keys:
                seen_keys.add(key)
                sources.append({
                    "type": "figure",
                    "figure_id": figure_id,
                    "page_number": pg_num,
                    "display_string": disp_str
                })
            continue

        # 3. Normal Text Page Source
        page_str = f"Page {pg_num}" if pg_num == pg_end else f"Pages {pg_num}-{pg_end}"
        key = ("page", pg_num, pg_end)
        if key not in seen_keys:
            seen_keys.add(key)
            sources.append({
                "type": "page",
                "page_number": pg_num,
                "page_end": pg_end,
                "display_string": page_str
            })

    # Sort sources logically by page number
    sources.sort(key=lambda s: s.get("page_number", 1))
    return sources

def format_sources_markdown(sources: List[Dict[str, Any]]) -> str:
    """
    Formats structured sources into clean markdown format required:
    
    Sources:
    * Page 12
    * Page 13
    """
    if not sources:
        return ""

    lines = ["\n\nSources:"]
    for src in sources:
        lines.append(f"* {src['display_string']}")
    return "\n".join(lines)

def attach_sources_to_answer(answer_text: str, sources: List[Dict[str, Any]], append_markdown: bool = False) -> str:
    """
    Appends formatted markdown sources to answer text deterministically if append_markdown=True.
    By default (append_markdown=False), returns the clean answer text without trailing Sources list.
    """
    if not answer_text or not answer_text.strip():
        return answer_text or ""

    # Clean existing Sources block if present
    if "\nSources:" in answer_text:
        answer_text = answer_text.split("\nSources:")[0].rstrip()
    elif "\n\nSources:" in answer_text:
        answer_text = answer_text.split("\n\nSources:")[0].rstrip()

    if not append_markdown:
        return answer_text

    if "couldn't find enough information" in answer_text.lower():
        return answer_text

    formatted_src = format_sources_markdown(sources)
    if formatted_src:
        return f"{answer_text.rstrip()}{formatted_src}"

    return answer_text
