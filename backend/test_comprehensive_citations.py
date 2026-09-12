# test_comprehensive_citations.py
import unittest
import sys

from services.citation_service import (
    extract_sources_from_metadata,
    format_sources_markdown,
    attach_sources_to_answer
)

class TestPDFMetadataCitations(unittest.TestCase):

    # =========================================================================
    # PDF CITATIONS & SOURCES TESTS (5 Test Cases)
    # =========================================================================

    def test_1_single_page_citation(self):
        """1. Single page citation: Extracts Page 5 from chunk metadata."""
        meta = [{"page_number": 5, "section": "Introduction"}]
        sources = extract_sources_from_metadata(meta)
        
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["type"], "page")
        self.assertEqual(sources[0]["page_number"], 5)
        self.assertEqual(sources[0]["display_string"], "Page 5")

        markdown = format_sources_markdown(sources)
        self.assertIn("Sources:\n* Page 5", markdown)
        print(f"\n[Test 1 Pass] Single Page Citation verified: '{sources[0]['display_string']}'")

    def test_2_multiple_page_citation(self):
        """2. Multiple page citation: Sourced from Pages 12 & 13; shows multiple bullet points in order."""
        meta = [
            {"page_number": 12, "section": "Financial Results"},
            {"page_number": 13, "section": "Financial Results"},
            {"page_number": 12, "section": "Overview"}  # duplicate page
        ]
        sources = extract_sources_from_metadata(meta)
        
        self.assertEqual(len(sources), 2)
        display_strings = [s["display_string"] for s in sources]
        self.assertEqual(display_strings, ["Page 12", "Page 13"])

        markdown = format_sources_markdown(sources)
        self.assertIn("* Page 12", markdown)
        self.assertIn("* Page 13", markdown)
        print(f"[Test 2 Pass] Multiple Page Citation verified: {display_strings}")

    def test_3_table_citation(self):
        """3. Table citation: Sourced from Table 2 on Page 15; formatted as 'Table 2 — Page 15'."""
        meta = [
            {"table_id": "table_2", "page_number": 15, "section": "Balance Sheet"}
        ]
        sources = extract_sources_from_metadata(meta)
        
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["type"], "table")
        self.assertEqual(sources[0]["display_string"], "Table 2 — Page 15")

        markdown = format_sources_markdown(sources)
        self.assertIn("* Table 2 — Page 15", markdown)
        print(f"[Test 3 Pass] Table Citation verified: '{sources[0]['display_string']}'")

    def test_4_figure_citation(self):
        """4. Figure citation: Sourced from Figure 4 on Page 18; formatted as 'Figure 4 — Page 18'."""
        meta = [
            {"figure_id": "figure_4", "page_number": 18, "section": "Model Design"}
        ]
        sources = extract_sources_from_metadata(meta)
        
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["type"], "figure")
        self.assertEqual(sources[0]["display_string"], "Figure 4 — Page 18")

        markdown = format_sources_markdown(sources)
        self.assertIn("* Figure 4 — Page 18", markdown)
        print(f"[Test 4 Pass] Figure Citation verified: '{sources[0]['display_string']}'")

    def test_5_no_page_invention(self):
        """5. No page invention test: Ensures sources attached to answer come strictly from stored metadata."""
        answer_body = "The company's revenue increased by 18% in FY2025."
        meta = [
            {"page_number": 12},
            {"page_number": 13}
        ]
        sources = extract_sources_from_metadata(meta)
        final_answer = attach_sources_to_answer(answer_body, sources, append_markdown=True)

        expected = (
            "The company's revenue increased by 18% in FY2025.\n\n"
            "Sources:\n"
            "* Page 12\n"
            "* Page 13"
        )

        self.assertEqual(final_answer.strip(), expected.strip())
        print(f"[Test 5 Pass] No Page Invention verified:\n{final_answer}")

if __name__ == "__main__":
    unittest.main()
