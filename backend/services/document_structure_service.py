# services/document_structure_service.py
"""
Isolated Document Structure Hierarchy Service for DocLens-AI.

Constructs deterministic document hierarchy from physical PDF layout and structural signals:
1. Explicit Markdown headers from parser (`pymupdf4llm` `#`, `##`, `###`, `####`)
2. Heading numbering patterns (`1`, `1.1`, `1.1.1`, `A.1`, `Appendix A`, `I.`, `Section 2`)
3. Table of Contents (TOC) hierarchy from PyMuPDF
4. Heading typography/layout metadata (font sizes)
5. Position/Section ordering

STRICT SAFETY & NON-HALLUCINATION RULES:
- Never classify repeated running headers/footers as topics.
- Never classify figure/table/code captions as topics unless explicit TOC structural evidence exists.
- Never classify bold lead-ins (e.g., "Note:", "Important:") as topics.
- Never invent missing hierarchy levels to fill gaps.
- Preserves exact original text, page numbers, heading order, parent-child links, source, and confidence.
"""

import re
import fitz
import pymupdf4llm
from typing import List, Dict, Any, Optional, Tuple, Set

class DocumentStructureService:
    """
    Manages document layout structure extraction, noise filtering, and hierarchy tree building.
    Statelessly extracts and caches the latest active document structure.
    """

    def __init__(self):
        self.current_structure: Optional[Dict[str, Any]] = None

    def clear(self):
        """Clears active document structure manifest from memory."""
        self.current_structure = None

    def get_current_structure(self) -> Optional[Dict[str, Any]]:
        """Returns active document structure manifest if available."""
        return self.current_structure

    def extract_structure(
        self,
        file_bytes: bytes,
        filename: str = "document.pdf",
        chunks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Main extraction entry point. Evaluates structural signals in strict priority:
        1. Markdown Headers -> 2. Numbering Patterns -> 3. TOC -> 4. Typography Font Size -> 5. Chunks/Fallback
        """
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        num_pages = len(doc)
        
        # 1. Detect running headers and footers to filter out repeating noise
        repeating_headers_footers = self._detect_running_headers_footers(doc)

        # 2. Collect candidate heading signals from all pages
        extracted_candidates = self._extract_heading_candidates(doc, file_bytes, repeating_headers_footers)
        doc.close()

        if not extracted_candidates and chunks:
            extracted_candidates = self._extract_candidates_from_chunks(chunks)

        if not extracted_candidates:
            # Document has no detectable headings; produce a single fallback root
            base_name = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
            extracted_candidates = [{
                "title": base_name,
                "level": 1,
                "page": 1,
                "source": "fallback",
                "confidence": 0.40
            }]

        # 3. Build tree and compute relationships
        tree, flat_nodes = self._build_hierarchy_tree(extracted_candidates, num_pages)

        manifest = {
            "success": True,
            "document_name": filename,
            "total_pages": num_pages,
            "total_topics": len(flat_nodes),
            "main_topics_count": len(tree),
            "max_depth": max((n["level"] for n in flat_nodes), default=1),
            "hierarchy_tree": tree,
            "flat_nodes": flat_nodes
        }

        self.current_structure = manifest
        return manifest

    def _detect_running_headers_footers(self, doc: fitz.Document) -> Set[str]:
        """
        Identifies repeated text occurring at top 12% or bottom 12% of pages across > 2 pages.
        """
        header_footer_counts: Dict[str, int] = {}

        for p_idx in range(len(doc)):
            page = doc.load_page(p_idx)
            p_height = page.rect.height or 792.0
            blocks = page.get_text("blocks")

            for b in blocks:
                # b format: (x0, y0, x1, y1, "text", block_no, block_type)
                if len(b) >= 5:
                    y0, y1, text = b[1], b[3], b[4].strip()
                    if not text:
                        continue

                    # Top 12% or Bottom 12% of page
                    if y0 < (p_height * 0.12) or y1 > (p_height * 0.88):
                        clean_line = " ".join(text.split()).lower()
                        header_footer_counts[clean_line] = header_footer_counts.get(clean_line, 0) + 1

        # Any header/footer text appearing on 2 or more pages is registered as noise
        noise_lines = set()
        for text_line, count in header_footer_counts.items():
            if count >= 2 and len(text_line) > 3:
                noise_lines.add(text_line)

        return noise_lines

    def _extract_heading_candidates(
        self,
        doc: fitz.Document,
        file_bytes: bytes,
        repeating_noise: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Collects headings prioritizing:
        Signal 1: Markdown headers (#, ##, ###)
        Signal 2: Numbering patterns (1, 1.1, 1.1.1, Appendix A, I., Section 2)
        Signal 3: Table of Contents (TOC)
        Signal 4: Font size typography
        """
        candidates: List[Dict[str, Any]] = []
        seen_headers = set()

        try:
            m_chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)
        except Exception:
            m_chunks = []

        page_texts: List[Tuple[int, str]] = []
        if m_chunks:
            for idx, chunk in enumerate(m_chunks):
                p_num = idx + 1
                if isinstance(chunk, dict):
                    p_num = chunk.get("metadata", {}).get("page_number", idx + 1)
                    text_content = chunk.get("text", "")
                else:
                    text_content = str(chunk)
                page_texts.append((p_num, text_content))

        for p_idx in range(len(doc)):
            p_num = p_idx + 1
            raw_t = doc.load_page(p_idx).get_text("text")
            if raw_t:
                page_texts.append((p_num, raw_t))

        header_regex = re.compile(r"^(#{1,6})\s+(.+)$")
        # Handles 1., 1.1, 1.1.1, 1.0, 2.3.4.1, Appendix A, A.1, Section 1, Roman numerals (I., II.)
        numbering_regex = re.compile(
            r"^(?:(?:Section|Chapter|Part|Appendix|Module)\s+([A-Z0-9\.\-]+)|(\d+(?:\.\d+)*|[A-Z]\.\d+(?:\.\d+)*|[IVXLCDM]+\.))\s*[:\.\-]?\s+(.+)$",
            re.IGNORECASE
        )

        for p_num, text_content in page_texts:
            lines = text_content.split("\n")
            for line in lines:
                line_str = line.strip()
                if not line_str or len(line_str) < 2:
                    continue

                # Filter running header/footer noise
                clean_check = " ".join(line_str.split()).lower()
                if clean_check in repeating_noise or re.search(r"^(?:page\s*\d+|\d+\s*of\s*\d+)$", clean_check):
                    continue

                # Filter Figure / Table / Code / Lead-in captions
                if self._is_caption_or_lead_in(line_str):
                    continue

                # Check Signal 1: Markdown Header
                m_head = header_regex.match(line_str)
                if m_head:
                    hashes, h_title = m_head.groups()
                    clean_title = h_title.strip()
                    lvl = len(hashes)

                    # Refine level if title contains explicit numbering pattern (e.g. # 2.3.4.1 -> Level 4)
                    m_num_check = numbering_regex.match(clean_title)
                    if m_num_check:
                        app_num, std_num, _ = m_num_check.groups()
                        if std_num and "." in std_num:
                            lvl = min(std_num.count(".") + 1, 6)

                    key = (p_num, clean_title.lower())
                    if clean_title and key not in seen_headers:
                        seen_headers.add(key)
                        candidates.append({
                            "title": clean_title,
                            "level": min(lvl, 6),
                            "page": p_num,
                            "source": "markdown",
                            "confidence": 0.95
                        })
                    continue

                # Check Signal 2: Numbering Pattern
                m_num = numbering_regex.match(line_str)
                if m_num:
                    app_num, std_num, h_title = m_num.groups()
                    num_str = std_num or app_num or ""
                    clean_title = line_str.strip()
                    
                    dots = num_str.count(".")
                    lvl = min(dots + 1, 6)
                    if num_str and not std_num:
                        lvl = 1

                    key = (p_num, clean_title.lower())
                    if clean_title and key not in seen_headers:
                        seen_headers.add(key)
                        candidates.append({
                            "title": clean_title,
                            "level": lvl,
                            "page": p_num,
                            "source": "numbering",
                            "confidence": 0.90
                        })
                    continue

                # Check Signal 2b: Standard Unnumbered Structural Sections (e.g. References, Bibliography, Abstract)
                std_sec_names = {"references", "bibliography", "works cited", "abstract", "acknowledgments", "acknowledgements"}
                if line_str.lower().strip() in std_sec_names:
                    clean_title = line_str.strip()
                    key = (p_num, clean_title.lower())
                    if clean_title and key not in seen_headers:
                        seen_headers.add(key)
                        candidates.append({
                            "title": clean_title,
                            "level": 1,
                            "page": p_num,
                            "source": "canonical_section",
                            "confidence": 0.90
                        })
                    continue

        # Signal 3: Embedded Table of Contents (TOC)
        toc = doc.get_toc()
        if toc:
            for lvl, title, page in toc:
                clean_title = title.strip()
                if not clean_title or self._is_caption_or_lead_in(clean_title):
                    continue
                key = (int(page), clean_title.lower())
                if key not in seen_headers:
                    seen_headers.add(key)
                    candidates.append({
                        "title": clean_title,
                        "level": min(max(int(lvl), 1), 6),
                        "page": int(page),
                        "source": "toc",
                        "confidence": 0.85
                    })

        # Signal 4: Typography / Layout metadata
        if not candidates:
            candidates = self._extract_by_typography(doc, seen_headers, repeating_noise)

        return candidates

    def _is_caption_or_lead_in(self, text: str) -> bool:
        """
        Determines if a string is a Figure/Table/Code caption, inline bold lead-in,
        or non-topic paragraph.
        """
        t = text.strip()

        # Reject figure / table / code / listing captions
        if re.search(r"^(?:Figure|Fig\.|Diagram|Chart|Table|Tbl\.|Listing|Code\s+Snippet)\s*\d+", t, re.I):
            return True

        # Reject inline bold lead-ins (e.g. Note:, Important:, Warning:, Step 1:)
        if re.search(r"^(?:Note|Important|Warning|Caution|Example|Definition|Step\s*\d+|Algorithm\s*\d+)\s*[:\.\-]", t, re.I):
            return True

        # Reject bold lead-in phrases that end with a colon
        if t.endswith(":") and len(t) < 40 and not any(w in t.lower() for w in ["section", "chapter", "contents", "summary"]):
            return True

        # Reject overly long paragraph lines (> 140 chars)
        if len(t) > 140:
            return True

        return False

    def _extract_by_typography(
        self,
        doc: fitz.Document,
        seen_headers: set,
        repeating_noise: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Extracts headings using font size and weight heuristics from PDF spans.
        """
        font_spans: List[Dict[str, Any]] = []

        for p_idx in range(len(doc)):
            page = doc.load_page(p_idx)
            p_num = p_idx + 1
            blocks = page.get_text("dict").get("blocks", [])

            for b in blocks:
                if b.get("type") != 0:
                    continue
                for l in b.get("lines", []):
                    line_text = "".join([s.get("text", "") for s in l.get("spans", [])]).strip()
                    if not line_text or len(line_text) < 3 or len(line_text) > 120:
                        continue

                    clean_check = " ".join(line_text.split()).lower()
                    if clean_check in repeating_noise or self._is_caption_or_lead_in(line_text):
                        continue

                    sizes = [s.get("size", 0) for s in l.get("spans", [])]
                    flags = [s.get("flags", 0) for s in l.get("spans", [])]
                    is_bold = any(f & 2 != 0 or "bold" in s.get("font", "").lower() for s, f in zip(l.get("spans", []), flags))

                    max_size = max(sizes) if sizes else 0
                    if max_size > 11 or is_bold:
                        font_spans.append({
                            "title": line_text,
                            "page": p_num,
                            "size": round(max_size, 1),
                            "is_bold": is_bold
                        })

        if not font_spans:
            return []

        size_set = sorted(list(set(s["size"] for s in font_spans if s["size"] >= 11)), reverse=True)
        size_level_map = {}
        for idx, sz in enumerate(size_set[:4]):
            size_level_map[sz] = idx + 1

        candidates = []
        for span in font_spans:
            sz = span["size"]
            lvl = size_level_map.get(sz, 3 if span["is_bold"] else 4)
            title = span["title"]
            key = (span["page"], title.lower())

            if key not in seen_headers:
                seen_headers.add(key)
                candidates.append({
                    "title": title,
                    "level": lvl,
                    "page": span["page"],
                    "source": "font_size",
                    "confidence": 0.75
                })

        return candidates

    def _extract_candidates_from_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback candidate extraction from chunk metadata."""
        seen = set()
        candidates = []
        for c in chunks:
            sec = (c.get("section") or c.get("chapter") or c.get("heading") or "").strip()
            page = int(c.get("page_number", c.get("page", 1)))
            if sec and sec.lower() != "general" and (page, sec.lower()) not in seen:
                seen.add((page, sec.lower()))
                candidates.append({
                    "title": sec,
                    "level": 1,
                    "page": page,
                    "source": "chunk_metadata",
                    "confidence": 0.60
                })
        return candidates

    def _build_hierarchy_tree(
        self,
        raw_candidates: List[Dict[str, Any]],
        total_pages: int
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Builds a normalized, deterministic tree structure:
        - Sorts by page number and heading order
        - Computes parent_id, children, sibling links, page ranges
        - Maps levels: 1 -> "Main Topic", 2 -> "Subtopic", 3+ -> "Nested Subtopic"
        - Preserves missing hierarchy levels without inventing dummy nodes!
        """
        raw_candidates.sort(key=lambda x: (x["page"]))

        # Deduplicate candidates on same page, preferring shorter clean heading titles over long paragraph strings
        deduped: List[Dict[str, Any]] = []
        for cand in raw_candidates:
            is_redundant = False
            for i, prev in enumerate(deduped):
                if prev["page"] == cand["page"]:
                    p_t = prev["title"].strip()
                    c_t = cand["title"].strip()
                    if p_t == c_t:
                        is_redundant = True
                        break
                    elif c_t.startswith(p_t) and len(c_t) > len(p_t):
                        is_redundant = True
                        break
                    elif p_t.startswith(c_t) and len(p_t) > len(c_t):
                        deduped[i] = cand
                        is_redundant = True
                        break
            if not is_redundant:
                deduped.append(cand)

        structured_nodes: List[Dict[str, Any]] = []
        for idx, item in enumerate(deduped):
            heading_order = idx + 1
            node_id = f"node_{heading_order:03d}"
            lvl = max(int(item.get("level", 1)), 1)
            
            # Special Node Type Detection (Appendix, References, Topic, Subtopic)
            t_lower = item["title"].lower()
            if "appendix" in t_lower:
                node_type = "appendix"
            elif any(w in t_lower for w in ["references", "bibliography", "works cited"]):
                node_type = "references"
            elif lvl == 1:
                node_type = "topic"
            else:
                node_type = "subtopic"

            level_name = "Main Topic" if lvl == 1 else ("Subtopic" if lvl == 2 else f"Level {lvl} Subtopic")

            structured_nodes.append({
                "node_id": node_id,
                "title": item["title"],
                "level": lvl,
                "level_name": level_name,
                "type": node_type,
                "page_start": int(item["page"]),
                "page_end": total_pages,
                "heading_order": heading_order,
                "parent_id": None,
                "children": [],
                "source": item.get("source", "unknown"),
                "confidence": item.get("confidence", 0.70),
                "relationships": {
                    "parent_title": None,
                    "sibling_prev": None,
                    "sibling_next": None,
                    "page_span": f"Page {item['page']}",
                    "subtopics_count": 0
                }
            })

        # Calculate page_end for each heading (spans until the next heading of same or higher level)
        for i in range(len(structured_nodes)):
            curr = structured_nodes[i]
            for j in range(i + 1, len(structured_nodes)):
                nxt = structured_nodes[j]
                if nxt["level"] <= curr["level"]:
                    curr["page_end"] = max(curr["page_start"], nxt["page_start"])
                    break
            
            p_start = curr["page_start"]
            p_end = curr["page_end"]
            curr["relationships"]["page_span"] = f"Page {p_start}" if p_start == p_end else f"Pages {p_start}-{p_end}"

        # Construct parent-child links without inventing dummy intermediate nodes
        root_nodes: List[Dict[str, Any]] = []
        stack: List[Dict[str, Any]] = []

        for node in structured_nodes:
            while stack and stack[-1]["level"] >= node["level"]:
                stack.pop()

            if stack:
                parent = stack[-1]
                node["parent_id"] = parent["node_id"]
                node["relationships"]["parent_title"] = parent["title"]
                parent["children"].append(node)
                parent["relationships"]["subtopics_count"] = len(parent["children"])
            else:
                root_nodes.append(node)

            stack.append(node)

        # Assign sibling sequence links
        def assign_siblings(nodes: List[Dict[str, Any]]):
            for k in range(len(nodes)):
                if k > 0:
                    nodes[k]["relationships"]["sibling_prev"] = nodes[k - 1]["title"]
                if k < len(nodes) - 1:
                    nodes[k]["relationships"]["sibling_next"] = nodes[k + 1]["title"]
                assign_siblings(nodes[k]["children"])

        assign_siblings(root_nodes)

        return root_nodes, structured_nodes

# Instantiate singleton service instance
document_structure_service = DocumentStructureService()
