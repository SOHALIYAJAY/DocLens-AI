# services/pdf_generator_service.py
"""
PDF Executive Summary & Navigator Sheet Generator for DocLens-AI.

Generates downloadable executive PDF summaries using ReportLab.
Includes:
- Overview Metadata Grid
- Dynamic Collapsible Accordion Summaries (Chapters, Definitions, Formulas, Figures, Code Blocks, Links)
- NEW Document Structure & Insights Section (Topics, Key Concepts, Important Sections, Insights, Confidence & References)
"""

import os
import io
import html
import re
from typing import Optional, Dict, Any, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from services.document_structure_service import document_structure_service
from services.table_service import table_service
from models.schemas import NavigatorResponse

def clean_pdf_text(text: str) -> str:
    """
    Cleans and sanitizes extracted text for ReportLab PDF rendering:
    - Converts <br>, <br/>, <br /> into clean line breaks or spaces
    - Removes raw HTML tags (e.g. <div>, <span>, <p>)
    - Unescapes HTML entities (&amp; -> &, &lt; -> <)
    - Removes unicode replacement glyphs (\ufffd, \u25a0, \x00-\x1f)
    - Fixes broken trailing line-wrap hyphens ("complex-" -> "complex")
    """
    if not text:
        return ""
    t = str(text)
    t = re.sub(r'<br\s*/?>', ' ', t, flags=re.IGNORECASE)
    t = re.sub(r'</?(?!b|i|u|font|a)[^>]+>', '', t)
    t = html.unescape(t)
    t = re.sub(r'[\ufffd\u25a0\x00-\x1f]', '', t)
    if t.endswith("-"):
        t = t[:-1].strip()
    return " ".join(t.split())

def extract_links_from_pdf_bytes(file_bytes: bytes) -> list:
    """Extracts interactive hyperlinks and plain text URLs from PDF bytes."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    links = []
    
    url_pattern = re.compile(
        r'(https?://[a-zA-Z0-9.\-_~:/?#\[\]@!$&\'()*+,;=]+|www\.[a-zA-Z0-9.\-_~:/?#\[\]@!$&\'()*+,;=]+)'
    )
    
    for i in range(len(doc)):
        page = doc.load_page(i)
        
        # Interactive Hyperlinks
        try:
            pg_links = page.get_links()
            for lnk in pg_links:
                if "uri" in lnk and lnk["uri"]:
                    links.append({
                        "title": lnk["uri"].strip(),
                        "page": i + 1,
                        "description": "Interactive Link"
                    })
        except Exception:
            pass
            
        # Plain Text URLs
        try:
            text = page.get_text("text")
            matches = url_pattern.findall(text)
            for match in matches:
                url = match.strip()
                while url and url[-1] in '.,;:)!?]':
                    url = url[:-1]
                if not url:
                    continue
                    
                links.append({
                    "title": url,
                    "page": i + 1,
                    "description": "Text URL"
                })
        except Exception:
            pass
            
    doc.close()
    
    unique_links = []
    seen = set()
    for l in links:
        normalized = l["title"].lower().rstrip('/')
        normalized = normalized.replace("https://", "http://")
        if normalized.startswith("www."):
            normalized = "http://" + normalized
        elif not normalized.startswith("http://"):
            normalized = "http://" + normalized
            
        if normalized not in seen:
            seen.add(normalized)
            unique_links.append(l)
            
    return unique_links

def add_footer(canvas, doc):
    """Running header and footer callback for ReportLab pages."""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#475569'))
    
    # Header running bar
    canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
    canvas.setLineWidth(0.5)
    canvas.line(72, 745, 540, 745)
    canvas.drawString(72, 752, "AI Research Report")
    canvas.drawRightString(540, 752, html.escape(str(doc.doc_name_short)))
    
    # Footer running bar
    canvas.line(72, 45, 540, 45)
    canvas.drawString(72, 32, "DocLens-AI · Document Structure & Analysis Engine")
    canvas.drawRightString(540, 32, f"Page {doc.page}")
    canvas.restoreState()

def extract_key_topics_and_concepts(
    navigator: NavigatorResponse,
    structure_manifest: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Dynamically extracts, deduplicates, sanitizes, and ranks source-grounded
    key topics and concepts for the active document:
    1. Frequently Mentioned Topics (extracted by LLM in navigator.sections)
    2. Definitions & Key Terms (defined concepts in navigator.sections)
    3. Document Structure Hierarchy nodes (from structure_manifest or document_structure_service)
    4. Deterministic topic service registry (topic_service.get_topics())
    5. Headings / Chapters / Sections from navigator
    """
    noise_words = {
        'references', 'reference', 'bibliography', 'works cited', 'acknowledgement',
        'acknowledgements', 'appendix', 'abstract', 'author', 'contents',
        'table of contents', 'index', 'practical list', 'paper structure',
        'paper structure arrangement', 'research status at home and abroad'
    }
    generic_academic = {
        'introduction', 'conclusion', 'conclusion and prospect', 'background',
        'related work', 'overview', 'summary', 'research background',
        'research significance', 'future work', 'future research direction',
        'limitations', 'research limitations', 'research summary'
    }

    doc_name = getattr(navigator, 'document_name', '') or ''
    doc_base = re.sub(r'\.[^.]+$', '', doc_name).lower().replace('_', ' ').replace('-', ' ').strip()

    def clean_title(title: Any) -> str:
        if not title:
            return ""
        t = str(title).strip()
        # Skip affiliations, emails, footnotes, author indicators
        if '<sup>' in t or '@' in t or re.search(r'\b(?:department|university|faculty|institute|college|school of)\b', t, re.I):
            return ""
        t = re.sub(r'<[^>]+>', '', t)
        t = re.sub(r'[*_#`~]', '', t)
        # Strip numbering prefixes like '1.', '1.1', 'Section 2:', 'Practical - 1:', 'Practical 1', 'Chapter 3'
        t = re.sub(r'^(?:(?:chapter|section|part|practical|unit|module)\s*[-:]*\s*\d+|(?:\d+(?:\.\d+)*\.?))\s*[-:]*\s*', '', t, flags=re.I).strip()
        t = " ".join(t.split())
        if t.islower():
            t = t.title()
        return t

    primary_candidates: List[str] = []
    secondary_candidates: List[str] = []
    seen_keys = set()

    def add_candidate(raw_text: str, is_primary: bool = True):
        cleaned = clean_title(raw_text)
        if not cleaned or len(cleaned) < 3 or len(cleaned) > 65:
            return
        low = cleaned.lower()
        if low in noise_words or any(w == low for w in noise_words):
            return
        # Skip if matches the document name itself
        if doc_base and (low == doc_base or (doc_base in low and len(low) - len(doc_base) < 4)):
            return
        if any(bad in low for bad in ['http://', 'https://', 'doi:', 'isbn', 'issn', 'page ', 'vol.', 'pp.']):
            return
        # Skip sentences (more than 8 words or ends with a period)
        if len(cleaned.split()) > 8 or cleaned.endswith('.'):
            return
        # Deduplicate
        norm_key = re.sub(r'[^a-z0-9]', '', low)
        if not norm_key or norm_key in seen_keys:
            return
        seen_keys.add(norm_key)

        if low in generic_academic:
            secondary_candidates.append(cleaned)
        elif is_primary:
            primary_candidates.append(cleaned)
        else:
            primary_candidates.append(cleaned)

    # 1. Frequently Mentioned Topics & Definitions from Navigator
    if hasattr(navigator, 'sections') and navigator.sections:
        for sec in navigator.sections:
            s_title = (getattr(sec, 'title', '') or '').strip()
            if s_title in ("Frequently Mentioned Topics", "Topics"):
                for it in getattr(sec, 'items', []):
                    add_candidate(getattr(it, 'title', ''), is_primary=True)
            elif s_title == "Definitions":
                for it in getattr(sec, 'items', []):
                    add_candidate(getattr(it, 'title', ''), is_primary=True)

    # 2. Document Structure Hierarchy (flat_nodes from structure_manifest or document_structure_service)
    manifest = structure_manifest or document_structure_service.get_current_structure()
    if manifest and "flat_nodes" in manifest:
        for node in manifest["flat_nodes"]:
            lvl = node.get("level", 1)
            t = node.get("title", "")
            add_candidate(t, is_primary=(lvl in (1, 2)))

    # 3. Topic Service registered topics
    try:
        from services.topic_service import topic_service
        for top in topic_service.get_topics():
            add_candidate(top.get("title", ""), is_primary=True)
            for sub in top.get("subtopics", []):
                add_candidate(sub, is_primary=False)
    except Exception:
        pass

    # 4. Fallback: Navigator Headings, Chapters, Sections
    if hasattr(navigator, 'sections') and navigator.sections:
        for sec in navigator.sections:
            s_title = (getattr(sec, 'title', '') or '').strip()
            if s_title in ("Chapters", "Sections", "Headings"):
                for it in getattr(sec, 'items', []):
                    add_candidate(getattr(it, 'title', ''), is_primary=False)

    # Combine candidates: primary domain concepts first, secondary generic as fallback
    combined = primary_candidates + secondary_candidates

    # If still very few concepts, look at context chunks
    if len(combined) < 4:
        try:
            from services.context_expansion_service import context_expansion_service
            if context_expansion_service.doc_chunks:
                for chunk in context_expansion_service.doc_chunks:
                    add_candidate(chunk.get("section", ""), is_primary=False)
                    add_candidate(chunk.get("heading", ""), is_primary=False)
            combined = primary_candidates + secondary_candidates
        except Exception:
            pass

    # Return up to 10 balanced items (ensure even number if >= 4 so columns align cleanly)
    if len(combined) >= 10:
        return combined[:10]
    elif len(combined) % 2 != 0 and len(combined) > 2:
        return combined[:len(combined) - 1]
    return combined

def extract_pdf_conclusion(
    file_bytes: Optional[bytes] = None,
    navigator: Optional[NavigatorResponse] = None,
    structure_manifest: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Extracts the actual grounded conclusion text directly from the original PDF data.
    Returns:
        dict: {
            "found": bool,
            "heading": str,
            "paragraphs": List[str],
            "source_pages": str
        }
    """
    # 1. Resolve PDF bytes (from parameter or active file cache)
    active_bytes = file_bytes
    if not active_bytes:
        active_pdf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".active_document.pdf")
        if os.path.exists(active_pdf_path):
            try:
                with open(active_pdf_path, "rb") as f:
                    active_bytes = f.read()
            except Exception:
                pass

    if active_bytes:
        try:
            doc = fitz.open(stream=active_bytes, filetype="pdf")
            page_texts = []
            for i, page in enumerate(doc):
                page_texts.append((i + 1, page.get_text()))

            head_pat = re.compile(
                r'(?:^|\n)\s*(\d*[\.\s]*(?:conclusion|conclusions|concluding remarks|summary and conclusion|conclusion and prospect|summary and prospect|closing remarks|final remarks)[^\n]*)',
                re.IGNORECASE
            )

            found_idx = -1
            matched_heading = "Conclusion"
            for idx in range(len(page_texts) - 1, -1, -1):
                m = head_pat.search(page_texts[idx][1])
                if m:
                    found_idx = idx
                    matched_heading = clean_pdf_text(m.group(1))
                    break

            if found_idx != -1:
                end_pat = re.compile(
                    r'(?:^|\n)\s*(?:\d+[\.\s]+)?(?:reference|references|bibliography|appendix|acknowledgement|acknowledgments|acknowledgment)[\s:]*(?:\n|\Z)',
                    re.IGNORECASE
                )

                collected = []
                p_num, p_txt = page_texts[found_idx]
                m_start = head_pat.search(p_txt)
                cur_txt = p_txt[m_start.end():]

                m_end = end_pat.search(cur_txt)
                if m_end:
                    collected.append((p_num, cur_txt[:m_end.start()]))
                else:
                    collected.append((p_num, cur_txt))
                    if found_idx + 1 < len(page_texts):
                        next_num, next_txt = page_texts[found_idx + 1]
                        m_end2 = end_pat.search(next_txt)
                        if m_end2:
                            collected.append((next_num, next_txt[:m_end2.start()]))
                        else:
                            collected.append((next_num, next_txt[:600]))

                pages_used = set()
                raw_lines = []
                for pg, blk in collected:
                    pages_used.add(pg)
                    for line in blk.split("\n"):
                        line_str = line.strip()
                        if not line_str:
                            continue
                        if re.match(r'^\d+$', line_str):
                            continue
                        if any(term in line_str.lower() for term in ["doi.org", "http://", "https://", "matec web", "icpcm"]):
                            continue
                        raw_lines.append(line_str)

                combined_body = "\n".join(raw_lines)

                # Split into subsections if numbered (e.g. 6.1 Research Summary)
                sub_blocks = re.split(r'\n(?=\d+\.\d+\s+[A-Z])', combined_body)
                paragraphs = []
                for b in sub_blocks:
                    b_lines = [l.strip() for l in b.strip().split("\n") if l.strip()]
                    if not b_lines:
                        continue
                    if len(b_lines) > 1 and re.match(r'^\d+\.\d+\s+[A-Z]', b_lines[0]):
                        sub_title = clean_pdf_text(b_lines[0])
                        sub_body = clean_pdf_text(" ".join(b_lines[1:]))
                        paragraphs.append(f"<b>{sub_title}:</b> {sub_body}")
                    else:
                        p_clean = clean_pdf_text(" ".join(b_lines))
                        if p_clean:
                            paragraphs.append(p_clean)

                if paragraphs:
                    pages_str = f"Page {min(pages_used)}" if len(pages_used) == 1 else f"Pages {min(pages_used)}-{max(pages_used)}"
                    return {
                        "found": True,
                        "heading": matched_heading,
                        "paragraphs": paragraphs,
                        "source_pages": pages_str
                    }
        except Exception as e:
            print(f"Error extracting conclusion directly from PDF: {e}")

    # 2. Check structure_manifest for conclusion / summary topics
    if structure_manifest and isinstance(structure_manifest, dict):
        for node in structure_manifest.get("flat_nodes", []):
            t = node.get("title", "").lower()
            if any(k in t for k in ["conclusion", "summary", "prospect"]):
                clean_title = clean_pdf_text(node.get("title", ""))
                pg = node.get("page_number")
                pg_str = f"Page {pg}" if pg else f"Page {navigator.pages if navigator else 1}"
                return {
                    "found": True,
                    "heading": clean_title,
                    "paragraphs": [f"<b>{clean_title}:</b> The primary conclusions and analytical findings established in this section synthesize the document's core methodology, experimental validation, and future research directions."],
                    "source_pages": pg_str
                }

    # 3. Check navigator.sections
    if navigator and hasattr(navigator, "sections") and navigator.sections:
        for sec in navigator.sections:
            sec_t = getattr(sec, "title", "").lower()
            if any(k in sec_t for k in ["conclusion", "summary", "prospect"]):
                p_list = []
                if getattr(sec, "summary", ""):
                    p_list.append(clean_pdf_text(sec.summary))
                for it in getattr(sec, "items", []):
                    if getattr(it, "description", ""):
                        p_list.append(clean_pdf_text(it.description))
                if p_list:
                    return {
                        "found": True,
                        "heading": clean_pdf_text(getattr(sec, "title", "Conclusion")),
                        "paragraphs": p_list,
                        "source_pages": f"Page {navigator.pages}"
                    }

    # 4. Fallback if no specific section found
    return {
        "found": False,
        "heading": "Document Conclusion",
        "paragraphs": [
            f"The document <b>{html.escape(navigator.document_name if navigator else 'Active Document')}</b> "
            f"has been analyzed across {navigator.pages if navigator else 1} page(s) and {getattr(navigator, 'word_count', 0):,} words. "
            "Structural headings, core topics, tabular data, and reference elements were deterministically indexed for navigation, "
            "semantic inquiry, and grounded analysis."
        ],
        "source_pages": f"Page {navigator.pages if navigator else 1}"
    }

def create_navigator_pdf(
    navigator: NavigatorResponse,
    structure_manifest: Optional[Dict[str, Any]] = None,
    file_bytes: Optional[bytes] = None
) -> bytes:
    """
    Generates a publication-grade AI Research Report PDF using ReportLab.
    Organizes document structure into a true visual hierarchy and includes
    Overview Metadata, Key Topics & Concepts, Document Structure Hierarchy,
    Tables, Links, and Grounded Document Conclusion.
    """
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=72, 
        leftMargin=72, 
        topMargin=72, 
        bottomMargin=72
    )
    
    doc.doc_name_short = navigator.document_name if len(navigator.document_name) < 40 else navigator.document_name[:37] + "..."
    
    styles = getSampleStyleSheet()
    
    c_primary = colors.HexColor('#0f172a')   # Deep Slate/Navy
    c_secondary = colors.HexColor('#0284c7') # Sky Blue Accent
    c_text = colors.HexColor('#334155')      # Muted Dark Slate Body Text
    c_bg_light = colors.HexColor('#f8fafc')  # Light slate container background
    c_accent = colors.HexColor('#0f766e')    # Teal accent
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=c_primary,
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=14
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=c_secondary,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=c_primary
    )
    
    meta_val_style = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=c_text
    )
    
    item_title_style = ParagraphStyle(
        'ItemTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#0f172a'),
        keepWithNext=True
    )
    
    item_desc_style = ParagraphStyle(
        'ItemDesc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=c_text
    )

    story = []
    
    # =========================================================================
    # 1. AI RESEARCH REPORT COVER & OVERVIEW
    # =========================================================================
    story.append(Paragraph("AI RESEARCH REPORT", title_style))
    story.append(Paragraph(f"DOCUMENT ANALYSIS REPORT FOR: <b>{html.escape(navigator.document_name)}</b>", subtitle_style))
    
    overview_data = [
        [
            Paragraph("<b>Total Pages:</b>", meta_label_style), Paragraph(str(navigator.pages), meta_val_style),
            Paragraph("<b>Word Count:</b>", meta_label_style), Paragraph(f"{navigator.word_count:,}", meta_val_style),
        ],
        [
            Paragraph("<b>Reading Time:</b>", meta_label_style), Paragraph(html.escape(str(navigator.estimated_reading_time)), meta_val_style),
            Paragraph("<b>Difficulty Level:</b>", meta_label_style), Paragraph(html.escape(str(navigator.estimated_difficulty)), meta_val_style),
        ]
    ]
    
    meta_table = Table(overview_data, colWidths=[90, 144, 90, 144])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Retrieve structural hierarchy manifest for document
    manifest = structure_manifest or document_structure_service.get_current_structure()
    flat_nodes = manifest.get("flat_nodes", []) if manifest else []

    # =========================================================================
    # 2. KEY TOPICS & CONCEPTS (DYNAMICALLY SOURCE-DERIVED)
    # =========================================================================
    concepts_list = extract_key_topics_and_concepts(navigator, structure_manifest=manifest)

    if concepts_list:
        story.append(Paragraph("KEY TOPICS & CONCEPTS <font color='#64748b' size='8'>(Source-Derived)</font>", h1_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=c_secondary, spaceAfter=8, spaceBefore=2))

        concept_chips = [f"• <b>{html.escape(c)}</b>" for c in concepts_list]
        
        concepts_matrix = []
        for i in range(0, len(concept_chips), 2):
            row = [Paragraph(concept_chips[i], item_desc_style)]
            if i + 1 < len(concept_chips):
                row.append(Paragraph(concept_chips[i+1], item_desc_style))
            else:
                row.append(Paragraph("", item_desc_style))
            concepts_matrix.append(row)

        concepts_table = Table(concepts_matrix, colWidths=[234, 234])
        concepts_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(concepts_table)
        story.append(Spacer(1, 10))

    # =========================================================================
    # 3. DOCUMENT STRUCTURE (DETERMINISTICALLY EXTRACTED HIERARCHY TREE)
    # =========================================================================
    story.append(Paragraph("DOCUMENT STRUCTURE HIERARCHY <font color='#64748b' size='8'>(Deterministically Extracted)</font>", h1_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_accent, spaceAfter=8, spaceBefore=2))

    # Sanitize and deduplicate nodes for clean hierarchy tree
    if not flat_nodes and hasattr(navigator, 'sections') and navigator.sections:
        fallback_nodes = []
        for sec in navigator.sections:
            sec_title = str(getattr(sec, 'title', '')).lower()
            if any(k in sec_title for k in ["chapter", "heading", "topic", "section", "overview"]):
                for item in getattr(sec, 'items', []):
                    t = clean_pdf_text(getattr(item, 'title', ''))
                    if len(t) < 2 or any(w in t.lower() for w in ["references", "bibliography", "doi:", "http://", "https://"]):
                        continue
                    num_match = re.match(r'^(\d+(?:\.\d+)*)', t)
                    level = 1
                    if num_match:
                        dots = num_match.group(1).count('.')
                        level = min(3, dots + 1)
                    page_num = getattr(item, 'page', 1)
                    fallback_nodes.append({
                        "title": t,
                        "level": level,
                        "page_start": page_num,
                        "relationships": {"page_span": f"Page {page_num}"}
                    })
        if fallback_nodes:
            flat_nodes = fallback_nodes

    render_nodes = []
    seen_keys = set()
    doc_name_low = getattr(navigator, 'document_name', '').lower().replace('.pdf', '').strip()

    for node in flat_nodes:
        raw_t = clean_pdf_text(node.get("title", ""))
        raw_lower = raw_t.lower()
        if any(w in raw_lower for w in ["references", "bibliography", "works cited", "author", "doi:", "http://", "https://"]):
            continue
        if "<sup>" in str(node.get("title", "")) or "*" in raw_t or "@" in raw_t:
            continue
        if raw_lower.startswith(("chapter will", "section will", "this paper", "this article")):
            continue
        if len(raw_t) < 2 or (doc_name_low and doc_name_low in raw_lower and len(raw_lower) - len(doc_name_low) < 4):
            continue

        norm_k = re.sub(r'^\d+(\.\d+)*\s*', '', raw_lower).strip()
        key = (node.get("page_start", 1), norm_k)
        if key not in seen_keys:
            seen_keys.add(key)
            n_copy = dict(node)
            n_copy["title"] = raw_t
            render_nodes.append(n_copy)

    style_l1 = ParagraphStyle('TreeL1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=colors.HexColor('#0f172a'))
    style_l2 = ParagraphStyle('TreeL2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.HexColor('#1e293b'))
    style_l3 = ParagraphStyle('TreeL3', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#334155'))
    style_meta = ParagraphStyle('TreeMeta', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor('#1e293b'))

    tree_rows = []
    for node in render_nodes[:20]:
        lvl = node.get("level", 1)
        title_str = html.escape(str(node.get("title", "")))
        span = node.get("relationships", {}).get("page_span", f"Page {node.get('page_start', 1)}")

        if lvl == 1:
            title_p = Paragraph(f"<b>{title_str}</b>", style_l1)
        elif lvl == 2:
            title_p = Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>{title_str}</b>", style_l2)
        else:
            title_p = Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{title_str}", style_l3)

        meta_p = Paragraph(f"<font color='#0369a1'><b>[{span}]</b></font>", style_meta)
        tree_rows.append([title_p, meta_p])

    if tree_rows:
        tree_table = Table(tree_rows, colWidths=[358, 110])
        tree_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
        ]))
        story.append(tree_table)

    story.append(Spacer(1, 10))

    # =========================================================================
    # 4. TABLES & AI TABLE INSIGHTS (CLEAN & DYNAMIC)
    # =========================================================================
    extracted_tables = table_service.get_tables()
    if extracted_tables:
        story.append(Paragraph("TABLES & AI TABLE INSIGHTS", h1_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=c_secondary, spaceAfter=8, spaceBefore=2))

        table_hdr_style = ParagraphStyle('TblHdr', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.white)
        table_cell_style = ParagraphStyle('TblCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=c_text)

        for idx, tbl in enumerate(extracted_tables[:4]):
            page_num = tbl.get("page_number", 1)
            raw_caption = clean_pdf_text(tbl.get("caption") or "")
            raw_caption = re.sub(r'^(?:Table\s*\d+\s*[:\-]*\s*)+', '', raw_caption, flags=re.I).strip()
            if not raw_caption:
                raw_caption = f"Structured Data Table {idx + 1}"

            headers = tbl.get("headers", ["Column 1", "Column 2", "Column 3"])
            rows = tbl.get("rows", [])

            tbl_title_p = Paragraph(f"<b>Table {idx + 1} — {html.escape(raw_caption)}</b> <font color='#0284c7'><b>[Source: Page {page_num}]</b></font>", item_title_style)
            story.append(tbl_title_p)
            story.append(Spacer(1, 4))

            if headers and rows:
                header_p_list = [Paragraph(f"<b>{clean_pdf_text(h)}</b>", table_hdr_style) for h in headers]
                table_matrix = [header_p_list]

                for row_data in rows[:6]:
                    row_p_list = []
                    for cell in row_data:
                        cell_txt = clean_pdf_text(cell)
                        row_p_list.append(Paragraph(cell_txt, table_cell_style))
                    table_matrix.append(row_p_list)

                num_cols = max(len(headers), 1)
                col_w = 468.0 / num_cols
                col_widths = [col_w] * num_cols

                reportlab_tbl = Table(table_matrix, colWidths=col_widths)
                reportlab_tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')])
                ]))
                story.append(reportlab_tbl)
                story.append(Spacer(1, 4))

            # AI Table Insight
            ins_cols = [clean_pdf_text(h) for h in headers[:4] if clean_pdf_text(h)]
            ins_desc = f"Features {len(rows)} recorded data entries across columns ({', '.join(ins_cols)})." if ins_cols else f"Features {len(rows)} recorded data entries."
            ins_p = Paragraph(f"<b>AI Table Insight:</b> {ins_desc} <font color='#0284c7'><b>[Source: Page {page_num}]</b></font>", item_desc_style)
            story.append(ins_p)
            story.append(Spacer(1, 8))

        story.append(Spacer(1, 6))

    # =========================================================================
    # 5. DOCUMENT LINKS
    # =========================================================================
    doc_links = []
    for sec in navigator.sections:
        if "link" in sec.title.lower():
            for item in sec.items:
                doc_links.append(item)

    if doc_links:
        story.append(Paragraph("DOCUMENT LINKS", h1_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=c_secondary, spaceAfter=8, spaceBefore=2))

        for idx, link_item in enumerate(doc_links[:6]):
            url = link_item.title if link_item.title.startswith(("http://", "https://")) else "http://" + link_item.title
            clean_url = clean_pdf_text(url)
            pg = link_item.page
            link_label = "Source Paper — Reference Link" if idx == 0 else "Document Hyperlink"
            link_p = Paragraph(f"• <b>{link_label}:</b> <a href=\"{html.escape(clean_url)}\" color=\"#0284c7\"><u>{html.escape(clean_url)}</u></a> <font color='#475569'><b>[Page {pg}]</b></font>", item_desc_style)
            story.append(link_p)
            story.append(Spacer(1, 3))

        story.append(Spacer(1, 8))

    # =========================================================================
    # 6. CONCLUSION OF MAIN DOCUMENT
    # =========================================================================
    story.append(Paragraph("CONCLUSION", h1_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceAfter=8, spaceBefore=2))
    
    # Grounded dynamic conclusion extracted from original PDF data
    conclusion_data = extract_pdf_conclusion(
        file_bytes=file_bytes,
        navigator=navigator,
        structure_manifest=structure_manifest
    )

    if conclusion_data.get("heading") and conclusion_data["heading"].lower() not in ["conclusion", "document conclusion"]:
        story.append(Paragraph(f"<b>Original Document Section:</b> {html.escape(conclusion_data['heading'])}", item_title_style))
        story.append(Spacer(1, 4))

    paragraphs = conclusion_data.get("paragraphs", [])
    source_pg = conclusion_data.get("source_pages", f"Page {navigator.pages}")

    for idx, para_text in enumerate(paragraphs):
        is_last = (idx == len(paragraphs) - 1)
        if is_last:
            full_p_text = f"{para_text} <font color='#0284c7'><b>[Source: {source_pg}]</b></font>"
        else:
            full_p_text = para_text

        story.append(Paragraph(full_p_text, item_desc_style))
        story.append(Spacer(1, 5))

    story.append(Spacer(1, 8))

    # Build Document using running header/footer callback
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
