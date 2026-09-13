# services/research_report_service.py
"""
AI Research Report Service for DocLens-AI.
Generates structured AI Research Reports driven directly by the normalized Document Structure Hierarchy tree.
"""

from typing import Dict, Any, Optional, List
from services.document_structure_service import document_structure_service
from services.context_expansion_service import context_expansion_service
from services.llm_service import generate_response

class ResearchReportService:
    """
    Synthesizes executive AI Research Reports by leveraging the normalized document structure
    hierarchy manifest (Main Topics, Subtopics, Sections, Page Ranges, Relationships).
    """

    def generate_report(
        self,
        focus_topic: Optional[str] = None,
        detail_level: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        Generates a structured research report based on the active document structure in memory.
        """
        structure = document_structure_service.get_current_structure()
        doc_chunks = context_expansion_service.doc_chunks

        doc_name = structure.get("document_name", "Document") if structure else "Document"
        total_pages = structure.get("total_pages", 1) if structure else 1
        flat_nodes = structure.get("flat_nodes", []) if structure else []
        tree_nodes = structure.get("hierarchy_tree", []) if structure else []

        # Build topic list summary from normalized hierarchy
        topic_summaries: List[str] = []
        for node in flat_nodes:
            t_name = node.get("title", "")
            t_level = node.get("level_name", "Topic")
            p_span = node.get("relationships", {}).get("page_span", "")
            parent = node.get("relationships", {}).get("parent_title", None)
            
            line = f"- [{t_level}] {t_name} ({p_span})"
            if parent:
                line += f" -> Child of: '{parent}'"
            topic_summaries.append(line)

        structure_digest = "\n".join(topic_summaries[:25]) if topic_summaries else "General Document Overview"

        # Create structured synthesis prompt
        prompt = f"""
You are an elite Senior AI Research Analyst.
Generate an extensive, highly structured AI Research Report based on the physical document hierarchy extracted below.

Document Title: {doc_name}
Total Pages: {total_pages}
Target Detail Level: {detail_level}
Focus Topic: {focus_topic or "All Document Topics"}

Extracted Document Structure Hierarchy:
{structure_digest}

Instructions for the Report:
1. Executive Overview & Mission: High-level overview of what this document covers.
2. Structured Topic Findings: For each main topic in the hierarchy, synthesize key findings, methodology, or equations.
3. Cross-Sectional Synthesis: Highlight structural relationships between parent topics and subtopics.
4. Key Takeaways & Actionable Conclusion: Summarize core outcomes and recommendations.

Format the output cleanly in GitHub Markdown using bold headings, bullet lists, and clear section breaks.
"""

        try:
            report_text = generate_response(prompt, context="")
        except Exception as e:
            report_text = f"# 📄 Research Report: {doc_name}\n\n## Executive Summary\nExtracted {len(flat_nodes)} structural topics across {total_pages} pages.\n\n### Document Hierarchy\n" + "\n".join(topic_summaries)

        return {
            "success": True,
            "document_name": doc_name,
            "report_markdown": report_text,
            "structure_overview": {
                "total_topics": len(flat_nodes),
                "main_topics_count": len(tree_nodes),
                "max_depth": structure.get("max_depth", 1) if structure else 1,
                "focus_topic": focus_topic or "Full Document"
            }
        }

# Instantiate singleton
research_report_service = ResearchReportService()
