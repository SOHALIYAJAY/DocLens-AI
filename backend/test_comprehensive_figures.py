# test_comprehensive_figures.py
import unittest
from unittest.mock import patch, MagicMock
import sys

from services.figure_service import FigureService, figure_service
from services.image_service import IMAGE_STORE

class TestFigureDiagramChartUnderstanding(unittest.TestCase):

    def setUp(self):
        figure_service.clear_figures()
        IMAGE_STORE.clear()

        # Seed sample images into IMAGE_STORE
        IMAGE_STORE["img_fig_4"] = {
            "base64_data": "fake_base64_string_fig_4",
            "format": "png",
            "bytes": b"fake_png_bytes_fig_4"
        }
        IMAGE_STORE["img_chart_2"] = {
            "base64_data": "fake_base64_string_chart_2",
            "format": "jpeg",
            "bytes": b"fake_jpeg_bytes_chart_2"
        }

        # Seed figure registry
        figure_service.add_figure({
            "figure_id": "figure_4",
            "image_id": "img_fig_4",
            "page_number": 4,
            "caption": "Figure 4: Transformer Architecture System Flowchart",
            "section": "Model Architecture",
            "document_id": "doc_test_123",
            "associated_text": "Figure 4 illustrates the encoder-decoder structure of the Transformer model.",
            "content_type": "figure"
        })

        figure_service.add_figure({
            "figure_id": "figure_2",
            "image_id": "img_chart_2",
            "page_number": 2,
            "caption": "Figure 2: Performance Evaluation Graph Across Benchmark Datasets",
            "section": "Experimental Results",
            "document_id": "doc_test_123",
            "associated_text": "Figure 2 plots the accuracy curve over 100 epochs.",
            "content_type": "figure"
        })

    # =========================================================================
    # FIGURE, DIAGRAM, CHART & IMAGE TESTS (5 Test Cases)
    # =========================================================================

    @patch("services.figure_service.analyze_image")
    def test_1_diagram_explanation(self, mock_analyze_image):
        """1. Diagram Explanation: 'Explain Figure 4' identifies Figure 4, runs Vision AI, and builds context block."""
        mock_analyze_image.return_value = {
            "title": "Transformer Architecture Diagram",
            "summary": "Shows multi-head attention and feedforward layers.",
            "explanation": "Inputs pass through positional encoding into multi-head attention modules.",
            "important_components": ["Multi-Head Attention", "Positional Encoding", "LayerNorm"],
            "relationships": ["Encoder outputs feed into Decoder attention layers"],
            "key_takeaways": ["Self-attention enables parallelized sequence processing"]
        }

        intent = figure_service.classify_visual_query("Explain Figure 4.")
        self.assertTrue(intent["is_visual_query"])
        self.assertTrue(intent["requires_vision_ai"])
        self.assertEqual(intent["target_num"], 4)

        matching_fig = figure_service.identify_relevant_figure("Explain Figure 4.", target_num=4)
        self.assertIsNotNone(matching_fig)
        self.assertEqual(matching_fig["figure_id"], "figure_4")

        evidence = figure_service.analyze_visual_evidence(matching_fig, "Explain Figure 4.")
        self.assertIsNotNone(evidence)
        mock_analyze_image.assert_called_once()

        formatted_block = figure_service.format_figure_context(matching_fig, evidence)
        self.assertIn("[Page 4, Figure figure_4]", formatted_block)
        self.assertIn("Transformer Architecture Diagram", formatted_block)
        print(f"\n[Test 1 Pass] Diagram Explanation verified for 'Figure 4'")

    @patch("services.figure_service.analyze_image")
    def test_2_chart_question(self, mock_analyze_image):
        """2. Chart Question: 'What trend is shown in the graph?' matches graph figure and extracts visual trend."""
        mock_analyze_image.return_value = {
            "title": "Benchmark Accuracy Curve",
            "summary": "Accuracy increases sharply up to epoch 40 before stabilizing at 98.4%.",
            "explanation": "The line graph displays steady positive growth in model accuracy.",
            "important_components": ["Epochs X-axis", "Accuracy Y-axis"],
            "relationships": ["Higher training epochs correlate with improved accuracy"],
            "key_takeaways": ["Model converges around epoch 40"]
        }

        intent = figure_service.classify_visual_query("What trend is shown in the graph?")
        self.assertTrue(intent["is_visual_query"])

        matching_fig = figure_service.identify_relevant_figure("What trend is shown in the graph?")
        self.assertIsNotNone(matching_fig)
        self.assertEqual(matching_fig["figure_id"], "figure_2")

        evidence = figure_service.analyze_visual_evidence(matching_fig, "What trend is shown in the graph?")
        self.assertIsNotNone(evidence)
        self.assertIn("Accuracy increases sharply", evidence["summary"])
        print(f"[Test 2 Pass] Chart Question trend analysis verified")

    def test_3_figure_caption_question(self):
        """3. Figure Caption Question: Caption inquiry matches metadata directly without Vision AI overhead."""
        intent = figure_service.classify_visual_query("What is the caption of Figure 2?")
        self.assertTrue(intent["is_visual_query"])
        self.assertFalse(intent["requires_vision_ai"])  # Caption questions do NOT trigger vision API calls!

        matching_fig = figure_service.identify_relevant_figure("What is the caption of Figure 2?", target_num=2)
        self.assertIsNotNone(matching_fig)
        self.assertEqual(matching_fig["caption"], "Figure 2: Performance Evaluation Graph Across Benchmark Datasets")
        print(f"[Test 3 Pass] Figure Caption Question answered directly without Vision AI overhead")

    @patch("services.figure_service.analyze_image")
    def test_4_image_question(self, mock_analyze_image):
        """4. Image Question: 'Describe the image on page 4' matches by page number and analyzes image."""
        mock_analyze_image.return_value = {
            "title": "Page 4 System Architecture",
            "summary": "Detailed diagram of network modules.",
            "explanation": "Component layout showing end-to-end pipeline.",
            "important_components": ["Input Module", "Output Module"],
            "relationships": [],
            "key_takeaways": []
        }

        matching_fig = figure_service.identify_relevant_figure("Describe the image on page 4.")
        self.assertIsNotNone(matching_fig)
        self.assertEqual(matching_fig["page_number"], 4)

        evidence = figure_service.analyze_visual_evidence(matching_fig, "Describe the image on page 4.")
        self.assertIsNotNone(evidence)
        print(f"[Test 4 Pass] Image Question matched page 4 successfully")

    def test_5_normal_text_question(self):
        """5. Normal Text Question: Non-visual question classifies as non-visual and proceeds with normal RAG."""
        intent = figure_service.classify_visual_query("What are the primary conclusions of the study?")
        self.assertFalse(intent["is_visual_query"])
        self.assertFalse(intent["requires_vision_ai"])
        print(f"[Test 5 Pass] Normal Text Question classified correctly: is_visual={intent['is_visual_query']}")

if __name__ == "__main__":
    unittest.main()
