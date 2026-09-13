# services/document_structure_service.py
"""
Isolated Document Structure Hierarchy Service for DocLens-AI.

Constructs deterministic document hierarchy from physical PDF layout and structural signals:
1. Explicit Markdown headers from parser (`pymupdf4llm` `#`, `##`, `###`, `####`)
2. Heading numbering patterns (`1`, `1.0`, `1.1`, `1.1.1`, `1.A`, `Appendix A`, `Article I`, `Section 1`, `Clause 2.1.A`)
3. Table of Contents (TOC) hierarchy from PyMuPDF
4. Heading typography/layout metadata (relative font sizes & bold weight)
5. Position/Section ordering

TARGETED FIXES ENFORCED:
- Case 1: 1.0, 2.0, 3.0 decimal L1 patterns correctly mapped to Level 1.
- Case 2: Bibliography/References state tracking suppresses citation false positives.
- Case 3: Legal structure patterns (Article I, Section 1.1, Clause 2.1.A) correctly nested.
- Case 4: Letter-suffix patterns (1.A, 1.B, 2.A) correctly recognized as Level 2 subtopics.
- Case 5: Typography-only multi-signal scoring (relative font vs body font, line length, standalone check).
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
        1. Markdown Headers -> 2. Numbering Patterns -> 3. TOC -> 4. Typography Font Size -> 5. Fallback
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
                if len(b) >= 5:
                    y0, y1, text = b[1], b[3], b[4].strip()
                    if not text:
                        continue

                    # Top 12% or Bottom 12% of page
                    if y0 < (p_height * 0.12) or y1 > (p_height * 0.88):
                        clean_line = " ".join(text.split()).lower()
                        header_footer_counts[clean_line] = header_footer_counts.get(clean_line, 0) + 1

        noise_lines = set()
        for text_line, count in header_footer_counts.items():
            if count >= 2 and len(text_line) > 3:
                noise_lines.add(text_line)

        return noise_lines

    def _calculate_numbering_level(self, num_str: str, prefix_type: str = "") -> int:
        """
        Calculates exact hierarchy level based on numbering pattern:
        - Case 1: 1., 1.0, 2.0, 3.0 -> Level 1 (Decimal L1)
        - Case 3: Article I -> Level 1, Section 1.1 -> Level 2, Clause 2.1.A -> Level 3
        - Case 4: Letter suffix (1.A, 1.B, 2.A) -> Level 2
        """
        clean_num = num_str.strip().rstrip(".")

        # Case 1: Decimal L1 (.0 suffix or plain single integer)
        if re.match(r"^\d+\.0+$", clean_num) or re.match(r"^\d+$", clean_num) or re.match(r"^[IVXLCDM]+$", clean_num, re.I):
            return 1

        # Case 3: Legal Prefixes
        pref_lower = prefix_type.lower()
        if pref_lower == "article":
            return 1
        elif pref_lower == "section":
            return 2 if ("." in clean_num and not clean_num.endswith(".0")) else 1
        elif pref_lower == "clause":
            return 3 if "." in clean_num else 2

        # Case 4: Letter Suffix (e.g. 1.A, 2.B)
        if re.match(r"^\d+\.[A-Z]$", clean_num, re.I):
            return 2

        # General multi-dot level (e.g. 1.1 -> L2, 1.1.1 -> L3, 2.3.4.1 -> L4)
        dots = clean_num.count(".")
        return min(dots + 1, 6)

    def _extract_heading_candidates(
        self,
        doc: fitz.Document,
        file_bytes: bytes,
        repeating_noise: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Collects headings prioritizing:
        Signal 1: Markdown headers (#, ##, ###)
        Signal 2: Numbering patterns (1., 1.0, 1.1, 1.A, Article I, Section 1.1)
        Signal 3: Table of Contents (TOC)
        Signal 4: Multi-signal Typography heuristics
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
        
        # Enhanced Numbering Regex (Handles 1., 1.0, 1.1, 1.A, Article I, Section 1.1, Clause 2.1.A)
        numbering_regex = re.compile(
            r"^(?:(Article|Section|Chapter|Part|Appendix|Clause|Module)\s+([A-Z0-9\.\-]+)|(\d+(?:\.[A-Z0-9]+)*|[A-Z]\.\d+(?:\.\d+)*|[IVXLCDM]+\.))\s*[:\.\-]?\s+(.+)$",
            re.IGNORECASE
        )

        std_sec_names = {"references", "bibliography", "works cited", "literature cited", "references and bibliography", "abstract", "acknowledgments"}

        in_references_section = False

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

                # Case 2: Bibliography Section Tracking
                if clean_check in std_sec_names:
                    if "reference" in clean_check or "biblio" in clean_check or "cited" in clean_check:
                        in_references_section = True

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

                # Case 2: Suppress numbered citations inside Bibliography section
                if in_references_section:
                    if re.match(r"^(?:\d+\.|\{\d+\}|\[\d+\])\s+[A-Z]", line_str):
                        continue

                # Check Signal 1: Markdown Header
                m_head = header_regex.match(line_str)
                if m_head:
                    hashes, h_title = m_head.groups()
                    clean_title = h_title.strip()
                    lvl = len(hashes)

                    if clean_title.lower() in std_sec_names:
                        lvl = 1
                    else:
                        m_num_check = numbering_regex.match(clean_title)
                        if m_num_check:
                            pref, pref_num, std_num, _ = m_num_check.groups()
                            num_str = std_num or pref_num or ""
                            if num_str:
                                lvl = self._calculate_numbering_level(num_str, prefix_type=pref or "")

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
                    pref, pref_num, std_num, h_title = m_num.groups()
                    num_str = std_num or pref_num or ""
                    clean_title = line_str.strip()
                    lvl = self._calculate_numbering_level(num_str, prefix_type=pref or "")

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

        # Signal 4: Case 5 Typography-Only Multi-Signal Scoring
        if not candidates:
            candidates = self._extract_by_typography(doc, seen_headers, repeating_noise)

        return candidates

    def _is_caption_or_lead_in(self, text: str) -> bool:
        """
        Determines if a string is a Figure/Table/Code caption, inline bold lead-in,
        or non-topic paragraph line.
        """
        t = text.strip()

        # Reject figure / table / code / listing captions
        if re.search(r"^(?:Figure|Fig\.|Diagram|Chart|Table|Tbl\.|Listing|Code\s+Snippet)\s*\d+", t, re.I):
            return True

        # Reject inline bold lead-ins (e.g. Note:, Important:, Warning:, Step 1:)
        if re.search(r"^(?:Note|Important|Warning|Caution|Example|Definition|Step\s*\d+|Algorithm\s*\d+)\s*[:\.\-]", t, re.I):
            return True

        # Reject bold lead-in phrases that end with a colon or period in paragraph text
        if t.endswith(":") and len(t) < 40 and not any(w in t.lower() for w in ["section", "chapter", "contents", "summary", "overview"]):
            return True

        # Reject body paragraph lines ending with period if long (> 65 chars)
        if len(t) > 65 and (t.endswith(".") or t.endswith("?") or t.endswith("!")):
            return True

        # Reject overly long paragraph lines (> 110 chars)
        if len(t) > 110:
            return True

        return False

    def _extract_by_typography(
        self,
        doc: fitz.Document,
        seen_headers: set,
        repeating_noise: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Case 5: Multi-Signal Typography & Layout Evidence Scoring.
        Determines body text font size per page and compares candidate font sizes relatively.
        """
        font_spans: List[Dict[str, Any]] = []
        all_sizes: List[float] = []

        for p_idx in range(len(doc)):
            page = doc.load_page(p_idx)
            p_num = p_idx + 1
            blocks = page.get_text("dict").get("blocks", [])

            for b in blocks:
                if b.get("type") != 0:
                    continue
                for l in b.get("lines", []):
                    line_text = "".join([s.get("text", "") for s in l.get("spans", [])]).strip()
                    if not line_text or len(line_text) < 3:
                        continue

                    sizes = [s.get("size", 0) for s in l.get("spans", [])]
                    flags = [s.get("flags", 0) for s in l.get("spans", [])]
                    is_bold = any(f & 2 != 0 or "bold" in s.get("font", "").lower() for s, f in zip(l.get("spans", []), flags))
                    max_size = round(max(sizes), 1) if sizes else 0.0

                    all_sizes.append(max_size)

                    clean_check = " ".join(line_text.split()).lower()
                    if clean_check in repeating_noise or self._is_caption_or_lead_in(line_text):
                        continue

                    font_spans.append({
                        "title": line_text,
                        "page": p_num,
                        "size": max_size,
                        "is_bold": is_bold
                    })

        if not font_spans or not all_sizes:
            return []

        # Find most frequent font size (Body Font Size)
        from collections import Counter
        size_counts = Counter(all_sizes)
        body_font_size = size_counts.most_common(1)[0][0] if size_counts else 10.0

        # Filter candidate spans strictly larger than body font size OR bold standalone titles
        heading_candidates = []
        for span in font_spans:
            sz = span["size"]
            title = span["title"]

            # Only accept lines strictly larger than body font or bold short titles (< 60 chars)
            if sz > body_font_size or (span["is_bold"] and len(title) < 60 and not title.endswith(".")):
                heading_candidates.append(span)

        if not heading_candidates:
            return []

        # Group distinct heading font sizes relatively
        distinct_heading_sizes = sorted(list(set(s["size"] for s in heading_candidates)), reverse=True)

        candidates = []
        for span in heading_candidates:
            sz = span["size"]
            title = span["title"]
            key = (span["page"], title.lower())

            # Relative level mapping based on font rank
            if sz == distinct_heading_sizes[0]:
                lvl = 1
            elif len(distinct_heading_sizes) > 1 and sz == distinct_heading_sizes[1]:
                lvl = 2
            else:
                lvl = 3 if span["is_bold"] else 4

            if key not in seen_headers:
                seen_headers.add(key)
                candidates.append({
                    "title": title,
                    "level": lvl,
                    "page": span["page"],
                    "source": "font_size",
                    "confidence": 0.75 if lvl == 1 else 0.65
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
