# test_topic_service.py
"""
Unit and Integration Tests for TopicService & Document Structure Awareness.
Validates intent classification, topic extraction, manifest formatting,
page citations, and grounded answer generation for questions like 'how many topic is exist'.
"""

import unittest
from typing import List, Dict, Any

from services.topic_service import TopicService, topic_service
from services.grounding_service import check_numeric_grounding, verify_grounding, generate_grounded_response
from services.citation_service import extract_sources_from_metadata, attach_sources_to_answer

class TestTopicService(unittest.TestCase):

    def setUp(self):
        self.service = TopicService()
        self.sample_chunks = [
            {
                "chunk_id": "c1",
                "document_id": "doc_test",
                "document_name": "ai_research.pdf",
                "page_number": 1,
                "section": "Introduction",
                "heading": "AI Overview",
                "text": "Artificial intelligence is advancing rapidly. This section provides an executive summary."
            },
            {
                "chunk_id": "c2",
                "document_id": "doc_test",
                "document_name": "ai_research.pdf",
                "page_number": 2,
                "section": "System Architecture",
                "heading": "Pipeline Design",
                "text": "The system architecture features a hybrid retrieval pipeline and cross-encoder reranking."
            },
            {
                "chunk_id": "c3",
                "document_id": "doc_test",
                "document_name": "ai_research.pdf",
                "page_number": 4,
                "section": "Experimental Evaluation",
                "heading": "Benchmark Results",
                "text": "Experiments on 50 benchmark questions show 98% accuracy and low latency."
            },
            {
                "chunk_id": "c4",
                "document_id": "doc_test",
                "document_name": "ai_research.pdf",
                "page_number": 6,
                "section": "Conclusion & Next Steps",
                "heading": "Future Work",
                "text": "In conclusion, document-level topic awareness significantly improves conversational RAG."
            }
        ]

    def test_1_classify_topic_intent_variations(self):
        """1. Verify accurate classification across diverse phrasing of topic count and list queries."""
        count_queries = [
            "how many topic is exist",
            "how many topics are there",
            "how many topic exist in this pdf",
            "how many sections are in this document",
            "total number of chapters",
            "what is the count of topics",
            "how much topic exist"
        ]
        for q in count_queries:
            intent = self.service.classify_topic_intent(q)
            self.assertTrue(intent["is_topic_query"], f"Failed for query: '{q}'")
            self.assertEqual(intent["query_type"], "count", f"Expected count for: '{q}'")

        list_queries = [
            "what topics exist in this PDF",
            "list all topics",
            "show the document outline",
            "table of contents",
            "what are the main sections"
        ]
        for q in list_queries:
            intent = self.service.classify_topic_intent(q)
            self.assertTrue(intent["is_topic_query"], f"Failed for query: '{q}'")
            self.assertEqual(intent["query_type"], "list", f"Expected list for: '{q}'")

        detail_query = "tell me about topic 2"
        detail_intent = self.service.classify_topic_intent(detail_query)
        self.assertTrue(detail_intent["is_topic_query"])
        self.assertEqual(detail_intent["query_type"], "detail")
        self.assertEqual(detail_intent["target_index"], 2)

        non_topic = "What was the total company revenue in 2024?"
        non_intent = self.service.classify_topic_intent(non_topic)
        self.assertFalse(non_intent["is_topic_query"])

        print("\n[Test 1 Pass] Topic intent classification verified for 13 query variations.")

    def test_2_extract_and_register_from_chunks(self):
        """2. Verify deterministic topic extraction, page numbering, and subtopics."""
        topics = self.service.extract_and_register_from_chunks(
            self.sample_chunks,
            filename="ai_research.pdf"
        )
        self.assertEqual(len(topics), 4)
        self.assertEqual(topics[0]["title"], "Introduction")
        self.assertEqual(topics[0]["page_number"], 1)
        self.assertEqual(topics[1]["title"], "System Architecture")
        self.assertEqual(topics[1]["page_number"], 2)
        self.assertEqual(topics[2]["title"], "Experimental Evaluation")
        self.assertEqual(topics[2]["page_number"], 4)
        self.assertEqual(topics[3]["title"], "Conclusion & Next Steps")
        self.assertEqual(topics[3]["page_number"], 6)

        print(f"[Test 2 Pass] Extracted {len(topics)} topics with exact page boundaries.")

    def test_3_format_topic_context_manifest(self):
        """3. Verify structured manifest context generation with explicit total counts."""
        self.service.extract_and_register_from_chunks(self.sample_chunks, filename="ai_research.pdf")
        intent = self.service.classify_topic_intent("how many topic is exist")
        manifest = self.service.format_topic_context(intent, "how many topic is exist")

        self.assertIn("[DOCUMENT STRUCTURE & TOPIC MANIFEST]", manifest)
        self.assertIn("Total Topics / Sections: 4", manifest)
        self.assertIn("1. Introduction — Page 1", manifest)
        self.assertIn("2. System Architecture — Page 2", manifest)
        self.assertIn("3. Experimental Evaluation — Page 4", manifest)
        self.assertIn("4. Conclusion & Next Steps — Page 6", manifest)

        print("[Test 3 Pass] Topic manifest formatting contains exact count and topic list.")

    def test_4_topic_source_citations(self):
        """4. Verify page citation metadata generation from topic registry."""
        self.service.extract_and_register_from_chunks(self.sample_chunks, filename="ai_research.pdf")
        intent = self.service.classify_topic_intent("what topics exist")
        context_block, raw_meta = self.service.retrieve_topic_context("what topics exist", intent)

        sources = extract_sources_from_metadata(raw_meta)
        pages = [s["page_number"] for s in sources]
        self.assertEqual(pages, [1, 2, 4, 6])

        print(f"[Test 4 Pass] Topic citations deterministically match pages {pages}.")

    def test_5_grounding_numeric_check_passes(self):
        """5. Verify numeric grounding check cleanly passes for topic count statements."""
        context_str = """
[DOCUMENT STRUCTURE & TOPIC MANIFEST]
Document: ai_research.pdf
Total Topics / Sections: 4

1. Introduction — Page 1
2. System Architecture — Page 2
3. Experimental Evaluation — Page 4
4. Conclusion & Next Steps — Page 6
"""
        draft_answer = "There are 4 topics in the uploaded PDF document: 1. Introduction (Page 1), 2. System Architecture (Page 2), 3. Experimental Evaluation (Page 4), and 4. Conclusion & Next Steps (Page 6)."

        numeric_pass = check_numeric_grounding(draft_answer, context_str)
        self.assertTrue(numeric_pass, "Numeric grounding check should pass for topic manifest.")

        print("[Test 5 Pass] Grounding check passes for topic count answer.")


if __name__ == "__main__":
    unittest.main()
