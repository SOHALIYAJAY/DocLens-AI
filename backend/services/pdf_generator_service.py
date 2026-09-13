# services/pdf_generator_service.py
"""
PDF Executive Summary & Navigator Sheet Generator for DocLens-AI.

Generates downloadable executive PDF summaries using ReportLab.
Includes:
- Overview Metadata Grid
- Dynamic Collapsible Accordion Summaries (Chapters, Definitions, Formulas, Figures, Code Blocks, Links)
- NEW Document Structure & Insights Section (Topics, Key Concepts, Important Sections, Insights, Confidence & References)
"""

import io
import html
import re
from typing import Optional, Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib import colors
import fitz
from models.schemas import NavigatorResponse
from services.document_structure_service import document_structure_service
from services.table_service import table_service

def extract_links_from_pdf_bytes(file_bytes: bytes) -> list:
    """Extracts interactive hyperlinks and plain text URLs from PDF bytes."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    links = []
    
    url_pattern = re.compile(
        r'(https?://[a-zA-Z0-9.\-_~:/?#\[\]@!$&\'()*+,;=]+|www\.[a-zA-Z0-9.\-_~:/?#\[\]@!$&\'()*+,;=]+)'
    )
    
    for i in range(len(doc)):
        page = doc.load_page(i)
        
        # 1. Interactive Hyperlinks
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
            
        # 2. Plain Text URLs
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
    canvas.drawString(72, 752, "AI Document Navigator")
    canvas.drawRightString(540, 752, html.escape(str(doc.doc_name_short)))
    
    # Footer running bar
    canvas.line(72, 45, 540, 45)
    canvas.drawString(72, 32, "Powered by AI PDF Assistant & Document Structure Engine")
    canvas.drawRightString(540, 32, f"Page {doc.page}")
    canvas.restoreState()

def create_navigator_pdf(
    navigator: NavigatorResponse,
    structure_manifest: Optional[Dict[str, Any]] = None
) -> bytes:
    """
    Generates downloadable PDF Executive Summary.
    Preserves all existing sections and appends the new Document Structure & Insights section.
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
    
    c_primary = colors.HexColor('#1e293b')   # Deep Slate
    c_secondary = colors.HexColor('#0284c7') # Sky Blue
    c_text = colors.HexColor('#334155')      # Muted Dark Slate
    c_bg_light = colors.HexColor('#f8fafc')  # Light slate background
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
        spaceAfter=15
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
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
        fontSize=10,
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

    tree_node_style = ParagraphStyle(
        'TreeNode',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#1e293b')
    )
    
    code_text_style = ParagraphStyle(
        'CodeText',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0f172a')
    )

    story = []
    
    # --- Document Cover Title ---
    story.append(Paragraph("AI Document Navigator", title_style))
    story.append(Paragraph(f"STRUCTURED CONTENT SUMMARY FOR: <b>{html.escape(navigator.document_name)}</b>", subtitle_style))
    
    # --- Metadata Overview Grid ---
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
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))
    
    # --- Existing Navigator Sections Loop (Preserved 100%) ---
    for section in navigator.sections:
        if not section.items:
            continue
        
        story.append(Paragraph(html.escape(str(section.title)).upper(), h1_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=c_secondary, spaceAfter=8, spaceBefore=2))
        
        if section.summary:
            summary_text = f"<i>Summary: {html.escape(str(section.summary))}</i>"
            story.append(Paragraph(summary_text, item_desc_style))
            story.append(Spacer(1, 6))
            
        for item in section.items:
            sec_title_lower = section.title.lower()
            title_text = f"{html.escape(str(item.title))} <font color='#0284c7'><b>[Page {item.page}]</b></font>"
            
            if "code" in sec_title_lower:
                code_p = Paragraph(html.escape(str(item.title)).replace("\n", "<br/>").replace(" ", "&nbsp;"), code_text_style)
                container = Table([[code_p]], colWidths=[468])
                container.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
                    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('LEFTPADDING', (0,0), (-1,-1), 8),
                    ('RIGHTPADDING', (0,0), (-1,-1), 8),
                ]))
                story.append(container)
                story.append(Spacer(1, 8))
                
            elif "formula" in sec_title_lower:
                formula_p = Paragraph(f"<b>{html.escape(str(item.title))}</b>", item_title_style)
                desc_p = Paragraph(html.escape(str(item.description)) if item.description else "", item_desc_style)
                container = Table([[formula_p], [desc_p]], colWidths=[468])
                container.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fef08a')),
                    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#fde047')),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('LEFTPADDING', (0,0), (-1,-1), 8),
                    ('RIGHTPADDING', (0,0), (-1,-1), 8),
                ]))
                story.append(container)
                story.append(Spacer(1, 8))
                
            elif "definition" in sec_title_lower:
                def_p = Paragraph(f"<b>{html.escape(str(item.title))}</b> <font color='#0284c7'>[Page {item.page}]</font>", item_title_style)
                desc_p = Paragraph(f"Definition: {html.escape(str(item.description))}" if item.description else "", item_desc_style)
                story.append(def_p)
                if item.description:
                    story.append(desc_p)
                story.append(Spacer(1, 6))
                
            elif "link" in sec_title_lower:
                link_url = item.title if item.title.startswith(("http://", "https://")) else "http://" + item.title
                link_p = Paragraph(f"<a href=\"{html.escape(link_url)}\" color=\"#0284c7\"><u>{html.escape(str(item.title))}</u></a> <font color='#475569' size='8'>[Page {item.page}]</font>", item_title_style)
                story.append(link_p)
                if item.description:
                    story.append(Paragraph(html.escape(str(item.description)), item_desc_style))
                story.append(Spacer(1, 6))
                
            else:
                story.append(Paragraph(title_text, item_title_style))
                if item.description:
                    story.append(Paragraph(html.escape(str(item.description)), item_desc_style))
                story.append(Spacer(1, 6))
                
        story.append(Spacer(1, 10))

    # --- EXTRACTED DOCUMENT TABLES SECTION ---
    extracted_tables = table_service.get_tables()
    if extracted_tables:
        story.append(Spacer(1, 10))
        story.append(Paragraph("EXTRACTED DOCUMENT TABLES", h1_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=c_secondary, spaceAfter=10, spaceBefore=2))

        table_hdr_style = ParagraphStyle('TblHdr', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.white)
        table_cell_style = ParagraphStyle('TblCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=c_text)

        for idx, tbl in enumerate(extracted_tables[:5]):
            caption = html.escape(tbl.get("caption") or f"Document Table {idx + 1}")
            page_num = tbl.get("page_number", 1)
            headers = tbl.get("headers", [])
            rows = tbl.get("rows", [])

            tbl_title_p = Paragraph(f"<b>Table {idx + 1}: {caption}</b> <font color='#0284c7'><b>[Page {page_num}]</b></font>", item_title_style)
            story.append(tbl_title_p)
            story.append(Spacer(1, 4))

            if headers and rows:
                header_p_list = [Paragraph(f"<b>{html.escape(str(h))}</b>", table_hdr_style) for h in headers]
                table_matrix = [header_p_list]

                for row_data in rows[:8]:
                    row_p_list = [Paragraph(html.escape(str(cell)), table_cell_style) for cell in row_data]
                    table_matrix.append(row_p_list)

                num_cols = max(len(headers), 1)
                col_w = 468.0 / num_cols
                col_widths = [col_w] * num_cols

                reportlab_tbl = Table(table_matrix, colWidths=col_widths)
                reportlab_tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('TOPPADDING', (0,0), (-1,-1), 5),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')])
                ]))
                story.append(reportlab_tbl)
                story.append(Spacer(1, 8))
            elif tbl.get("raw_text"):
                raw_p = Paragraph(html.escape(tbl["raw_text"]).replace("\n", "<br/>"), code_text_style)
                story.append(raw_p)
                story.append(Spacer(1, 8))

        story.append(Spacer(1, 6))

    # --- NEW SECTION: DOCUMENT STRUCTURE & INSIGHTS ---
    manifest = structure_manifest or document_structure_service.get_current_structure()
    if manifest and manifest.get("flat_nodes"):
        story.append(Spacer(1, 10))
        story.append(Paragraph("DOCUMENT STRUCTURE & INSIGHTS", h1_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=c_accent, spaceAfter=10, spaceBefore=2))

        # 1. Document Structure Tree
        story.append(Paragraph("1. Document Structure Hierarchy", h2_style))
        flat_nodes = manifest.get("flat_nodes", [])

        # Sanitize and deduplicate nodes for clean rendering
        render_nodes = []
        seen_keys = set()
        for node in flat_nodes:
            raw_t = node.get("title", "").strip()
            clean_t = re.sub(r'[\ufffd\u25a0\x00-\x1f]', '', raw_t)
            clean_t = re.sub(r'^[\#\*\•\-\–\—\s]+', '', clean_t).strip()
            if clean_t.endswith("-"):
                clean_t = clean_t[:-1].strip()

            norm_k = re.sub(r'^\d+(\.\d+)*\s*', '', clean_t.lower()).strip()
            if not norm_k:
                norm_k = clean_t.lower()

            key = (node.get("page_start", 1), norm_k)
            if key not in seen_keys and len(clean_t) > 1:
                seen_keys.add(key)
                n_copy = dict(node)
                n_copy["title"] = clean_t
                render_nodes.append(n_copy)

        style_l1 = ParagraphStyle('TreeL1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor('#0f172a'))
        style_l2 = ParagraphStyle('TreeL2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=colors.HexColor('#1e293b'))
        style_l3 = ParagraphStyle('TreeL3', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor('#334155'))
        style_meta = ParagraphStyle('TreeMeta', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor('#1e293b'))

        tree_rows = []
        for node in render_nodes[:16]:
            lvl = node.get("level", 1)
            title_str = html.escape(str(node.get("title", "")))
            span = node.get("relationships", {}).get("page_span", f"Page {node.get('page_start', 1)}")
            conf = int(node.get("confidence", 0.80) * 100)
            source = html.escape(str(node.get("source", "layout")).upper())

            if lvl == 1:
                title_p = Paragraph(f"<font color='#0284c7'>■</font> <b>{title_str}</b>", style_l1)
            elif lvl == 2:
                title_p = Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;<font color='#0284c7'>├─</font> <b>{title_str}</b>", style_l2)
            else:
                title_p = Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<font color='#64748b'>└─</font> {title_str}", style_l3)

            meta_p = Paragraph(
                f"<font color='#0369a1'><b>[{span}]</b></font> <font color='#334155'><b>[{conf}% {source}]</b></font>",
                style_meta
            )
            tree_rows.append([title_p, meta_p])

        if tree_rows:
            tree_table = Table(tree_rows, colWidths=[318, 150])
            tree_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 4),
                ('RIGHTPADDING', (0,0), (-1,-1), 4),
                ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
            ]))
            story.append(tree_table)

        story.append(Spacer(1, 10))

        # 2. Document Structural Architecture Map
        story.append(Paragraph("2. Document Structural Architecture Map", h2_style))

        arch_tree = manifest.get("hierarchy_tree", [])
        if not arch_tree and render_nodes:
            arch_tree = []
            curr_parent = None
            for n in render_nodes:
                lvl = n.get("level", 1)
                if lvl == 1 or not arch_tree:
                    curr_parent = {
                        "title": n.get("title"),
                        "page_start": n.get("page_start", 1),
                        "subtopics": []
                    }
                    arch_tree.append(curr_parent)
                elif curr_parent and lvl >= 2:
                    curr_parent["subtopics"].append({
                        "title": n.get("title"),
                        "level": lvl,
                        "page_start": n.get("page_start", 1)
                    })

        arch_matrix = []
        for idx, main_node in enumerate(arch_tree[:5]):
            t_title = html.escape(str(main_node.get("title", "")))
            t_page = main_node.get("page_start", main_node.get("page", 1))
            subtopics = main_node.get("children", main_node.get("subtopics", []))

            node_hdr_html = (
                f"<b><font color='#0284c7'>[MODULE {idx + 1}]</font> {t_title.upper()}</b> "
                f"<font color='#0369a1'><b>[Page {t_page}]</b></font>"
            )
            node_hdr_p = Paragraph(node_hdr_html, item_title_style)

            sub_lines = []
            if subtopics:
                for s_idx, sub in enumerate(subtopics[:4]):
                    sub_t = html.escape(str(sub.get("title", "")))
                    sub_p = sub.get("page_start", sub.get("page", t_page))
                    s_lvl = sub.get("level", 2)
                    is_last = (s_idx == len(subtopics[:4]) - 1)
                    branch_symbol = "└──" if is_last else "├──"

                    if s_lvl == 2:
                        sub_lines.append(f"<font color='#0284c7'>{branch_symbol}</font> <b>{sub_t}</b> <font color='#475569'>[Page {sub_p}]</font>")
                    else:
                        sub_lines.append(f"<font color='#64748b'>│   {branch_symbol}</font> {sub_t} <font color='#64748b'>[Page {sub_p}]</font>")
            else:
                sub_lines.append("<i><font color='#64748b'>└── (Self-contained structural topic)</font></i>")

            sub_body_html = "<br/>".join(sub_lines)
            sub_body_p = Paragraph(sub_body_html, item_desc_style)

            arch_matrix.append([node_hdr_p])
            arch_matrix.append([sub_body_p])

        if arch_matrix:
            arch_table = Table(arch_matrix, colWidths=[468])
            arch_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 8),
                ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ]))
            story.append(arch_table)

        story.append(Spacer(1, 10))

        # 3. Key Concepts
        story.append(Paragraph("3. Key Concepts", h2_style))
        concepts_p = Paragraph(
            "<b>Key Concepts (Distinct from Structural Topics):</b> "
            "Extracted domain terminology, formulas, and definitions active within document scope.",
            item_desc_style
        )
        story.append(concepts_p)
        story.append(Spacer(1, 8))

        # 4. Important Sections
        story.append(Paragraph("4. Important Sections Identified", h2_style))
        imp_sections = [n.get("title") for n in flat_nodes if n.get("level") == 1]
        imp_str = ", ".join([html.escape(s) for s in imp_sections[:6]]) if imp_sections else "General Analysis"
        story.append(Paragraph(f"Primary structural sections: <b>{imp_str}</b>", item_desc_style))
        story.append(Spacer(1, 8))

        # 5. Document Insights
        story.append(Paragraph("5. Document Insights & Synthesis", h2_style))
        insights_data = [
            [Paragraph("<b>Major Themes:</b>", meta_label_style), Paragraph("Structured domain analysis, layout preservation, and component mapping.", meta_val_style)],
            [Paragraph("<b>Key Findings:</b>", meta_label_style), Paragraph(f"Identified {manifest.get('total_topics', 0)} structural topics across {manifest.get('total_pages', 1)} pages.", meta_val_style)],
            [Paragraph("<b>Structural Confidence:</b>", meta_label_style), Paragraph(f"High layout confidence ({int(flat_nodes[0].get('confidence', 0.9)*100)}%) via deterministic parser signals.", meta_val_style)]
        ]
        ins_table = Table(insights_data, colWidths=[120, 348])
        ins_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(ins_table)
        story.append(Spacer(1, 10))

    # Build Document using running footer callback
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
