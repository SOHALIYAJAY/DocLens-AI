# services/figure_service.py
"""
Figure Service for DocLens-AI Chatbot.
Handles figure/diagram/chart extraction, figure-aware retrieval, selective Vision AI analysis,
and multi-source context fusion (metadata, caption, text, visual evidence).
"""

import re
from typing import List, Dict, Any, Optional
from services.image_service import get_image_base64, IMAGE_STORE
from services.vision_service import analyze_image
from services.llm_service import safe_print

class FigureService:
    def __init__(self):
        self.figures: List[Dict[str, Any]] = []

    def clear_figures(self):
        """Clears stored figure registry."""
        self.figures.clear()

    def get_figures(self) -> List[Dict[str, Any]]:
        """Returns all registered figures."""
        return self.figures

    def add_figure(self, figure_data: Dict[str, Any]):
        """
        Registers a figure/image object preserving metadata:
        - figure_id
        - image_id
        - page_number
        - caption
        - section
        - document_id
        - associated_text
        - content_type
        """
        fig_id = figure_data.get("figure_id") or f"figure_{len(self.figures) + 1}"
        image_id = figure_data.get("image_id", "")
        page_number = int(figure_data.get("page_number", figure_data.get("page", 1)))
        caption = figure_data.get("caption", "")
        section = figure_data.get("section", "General")
        document_id = figure_data.get("document_id", "doc_default")
        associated_text = figure_data.get("associated_text", "")
        content_type = figure_data.get("content_type", "figure")

        structured_fig = {
            "figure_id": fig_id,
            "image_id": image_id,
            "page_number": page_number,
            "caption": caption,
            "section": section,
            "document_id": document_id,
            "associated_text": associated_text,
            "content_type": content_type
        }

        # Avoid duplicates by figure_id or image_id
        for idx, existing in enumerate(self.figures):
            if existing["figure_id"] == fig_id and existing["page_number"] == page_number:
                if image_id and not existing["image_id"]:
                    existing["image_id"] = image_id
                self.figures[idx] = existing
                return

        self.figures.append(structured_fig)

    def extract_and_register_from_chunks(self, chunks: List[Dict[str, Any]], extracted_images: List[Dict[str, Any]] = None):
        """
        Scans document chunks and extracted images to build the figure registry.
        """
        fig_counter = 0

        # Map page numbers to extracted image_ids
        page_image_map = {}
        if extracted_images:
            for img in extracted_images:
                pg = int(img.get("page", 1))
                img_id = img.get("image_id", "")
                if pg not in page_image_map:
                    page_image_map[pg] = []
                page_image_map[pg].append(img_id)

        for chunk in chunks:
            content_type = chunk.get("content_type", "")
            c_text = chunk.get("text", "")
            pg_num = int(chunk.get("page_number", chunk.get("page", 1)))

            is_fig = content_type in ("figure", "image") or bool(re.search(r"(?:Figure|Fig\.|Diagram|Chart|Graph)\s*\d+", c_text, re.IGNORECASE))

            if is_fig:
                fig_counter += 1
                fig_id = chunk.get("figure_id") or f"figure_{fig_counter}"
                caption = chunk.get("caption", "")

                if not caption:
                    cap_match = re.search(r"(?:Figure|Fig\.|Diagram|Chart|Graph)\s*\d+[:\.-]?\s*([^\n]+)", c_text, re.IGNORECASE)
                    if cap_match:
                        caption = cap_match.group(0).strip()

                # Get matching image_id for page if available
                img_ids = page_image_map.get(pg_num, [])
                matching_img_id = img_ids[0] if img_ids else ""

                self.add_figure({
                    "figure_id": fig_id,
                    "image_id": matching_img_id,
                    "page_number": pg_num,
                    "caption": caption,
                    "section": chunk.get("section", "General"),
                    "document_id": chunk.get("document_id", "doc_default"),
                    "associated_text": c_text,
                    "content_type": content_type or "figure"
                })

        # Register any remaining extracted images that were not explicitly tagged in chunks
        if extracted_images:
            for img in extracted_images:
                pg = int(img.get("page", 1))
                img_id = img.get("image_id", "")
                already_registered = any(f["image_id"] == img_id for f in self.figures)
                if not already_registered:
                    fig_counter += 1
                    self.add_figure({
                        "figure_id": f"figure_img_{fig_counter}",
                        "image_id": img_id,
                        "page_number": pg,
                        "caption": f"Image on page {pg}",
                        "section": "General",
                        "document_id": "doc_default",
                        "associated_text": "",
                        "content_type": "image"
                    })

    def classify_visual_query(self, query: str) -> Dict[str, Any]:
        """
        Classifies whether a query is asking about a figure, diagram, chart, graph, or image.
        """
        if not query:
            return {"is_visual_query": False, "requires_vision_ai": False, "target_num": None}

        q_lower = query.lower()

        visual_keywords = [
            "figure", "fig", "diagram", "chart", "graph", "plot", "image", "illustration",
            "architecture", "flowchart", "draw", "picture", "trend", "visual", "show"
        ]

        is_visual = any(kw in q_lower for kw in visual_keywords)

        # Detect figure number reference (e.g. "Figure 4" or "Fig 2")
        fig_num_match = re.search(r"(?:figure|fig|diagram|chart|graph)\s*(\d+)", q_lower)
        target_num = int(fig_num_match.group(1)) if fig_num_match else None

        # Check if question requires Vision AI visual understanding
        # (e.g. "Explain Figure 4", "What trend is shown in graph?", "What does diagram show?")
        caption_only = any(w in q_lower for w in ["caption", "title of figure", "name of figure"])
        requires_vision = is_visual and not caption_only

        return {
            "is_visual_query": is_visual,
            "requires_vision_ai": requires_vision,
            "target_num": target_num
        }

    def identify_relevant_figure(self, query: str, target_num: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Identifies top relevant figure/image matching the query or target figure number.
        """
        if not self.figures:
            return None

        # 1. Match by exact figure number (e.g. "Figure 4" -> figure_4 or page 4)
        if target_num is not None:
            for fig in self.figures:
                f_id = fig["figure_id"].lower()
                if f"figure_{target_num}" in f_id or f"fig_{target_num}" in f_id or f_id == f"figure_{target_num}":
                    return fig
                if fig["page_number"] == target_num:
                    return fig

        # 2. Match by page reference (e.g. "page 3")
        pg_match = re.search(r"\bpage\s*(\d+)\b", query.lower())
        if pg_match:
            pg = int(pg_match.group(1))
            for fig in self.figures:
                if fig["page_number"] == pg:
                    return fig

        # 3. Match by keyword overlap with caption / section / text
        q_tokens = set(re.findall(r"\w+", query.lower()))
        best_fig = None
        best_score = -1

        for fig in self.figures:
            score = 0
            searchable = f"{fig['figure_id']} {fig['caption']} {fig['section']} {fig['associated_text']}".lower()
            for token in q_tokens:
                if len(token) > 2 and token in searchable:
                    score += 1
                    if token in fig['caption'].lower():
                        score += 2
            if score > best_score:
                best_score = score
                best_fig = fig

        if best_score > 0:
            return best_fig

        return self.figures[0] if self.figures else None

    def analyze_visual_evidence(self, figure: Dict[str, Any], query: str) -> Optional[Dict[str, Any]]:
        """
        Selectively runs Groq Vision AI on relevant figure image if available.
        """
        if not figure or not figure.get("image_id"):
            return None

        img_data = get_image_base64(figure["image_id"])
        if not img_data:
            return None

        try:
            safe_print(f"[Vision AI] Analyzing visual evidence for figure '{figure['figure_id']}'...")
            vision_result = analyze_image(
                image_base64=img_data["base64_data"],
                image_format=img_data["format"],
                prompt=query
            )
            return vision_result
        except Exception as e:
            safe_print(f"[Vision AI Warning]: Failed to analyze image ({str(e)}). Proceeding with text context.")
            return None

    def format_figure_context(self, figure: Dict[str, Any], visual_evidence: Optional[Dict[str, Any]] = None) -> str:
        """
        Combines figure metadata, caption, surrounding text, and visual evidence into rich context block.
        """
        fig_id = figure["figure_id"]
        page_num = figure["page_number"]
        caption = figure.get("caption", "")
        section = figure.get("section", "General")
        text = figure.get("associated_text", "")

        lines = [
            "=== VISUAL FIGURE & DIAGRAM EVIDENCE DETECTED ===",
            f"[Page {page_num}, Figure {fig_id}] [Section: {section}]",
            f"Caption: {caption if caption else 'None'}"
        ]

        if text:
            lines.append(f"Text Context around Figure:\n{text}")

        if visual_evidence and isinstance(visual_evidence, dict):
            lines.append("\n=== VISION AI ANALYSIS RESULT ===")
            if visual_evidence.get("title"):
                lines.append(f"Visual Title: {visual_evidence.get('title')}")
            if visual_evidence.get("summary"):
                lines.append(f"Visual Summary: {visual_evidence.get('summary')}")
            if visual_evidence.get("explanation"):
                lines.append(f"Visual Detailed Explanation: {visual_evidence.get('explanation')}")
            if visual_evidence.get("important_components"):
                lines.append(f"Components: {', '.join(visual_evidence.get('important_components'))}")
            if visual_evidence.get("relationships"):
                lines.append(f"Flow & Relationships: {', '.join(visual_evidence.get('relationships'))}")
            if visual_evidence.get("key_takeaways"):
                lines.append(f"Key Takeaways: {', '.join(visual_evidence.get('key_takeaways'))}")

        lines.append("=================================================\n")
        return "\n".join(lines)


# Global singleton instance
figure_service = FigureService()
