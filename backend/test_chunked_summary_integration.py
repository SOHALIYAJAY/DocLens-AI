# test_chunked_summary_integration.py
import unittest
from unittest.mock import patch, MagicMock
from services.llm_service import generate_summary

class TestChunkedSummaryIntegration(unittest.TestCase):

    @patch("services.llm_service.get_groq_client")
    def test_small_pdf_summary_flow(self, mock_get_client):
        """Test small PDF (<6500 tokens) single pass summarization flow."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock completion response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Small PDF summary result."
        mock_client.chat.completions.create.return_value = mock_response

        small_text = "This is a small PDF text document for testing single-pass summary."
        result = generate_summary(small_text, "small")

        self.assertEqual(result, "Small PDF summary result.")
        # Groq client should be called exactly 1 time for a small PDF
        self.assertEqual(mock_client.chat.completions.create.call_count, 1)
        print("\n[Test Pass] Small PDF single-pass flow executed correctly")

    @patch("services.llm_service.get_groq_client")
    @patch("services.llm_service.chunk_text_by_tokens")
    @patch("services.llm_service.count_tokens")
    def test_large_pdf_chunked_summary_flow(self, mock_count_tokens, mock_chunk_text, mock_get_client):
        """Test large PDF Map-Reduce multi-chunk summarization flow."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock API calls: 2 chunk summaries + 1 final summary = 3 calls
        mock_resp_1 = MagicMock()
        mock_resp_1.choices[0].message.content = "Summary of Chunk 1"
        mock_resp_2 = MagicMock()
        mock_resp_2.choices[0].message.content = "Summary of Chunk 2"
        mock_resp_final = MagicMock()
        mock_resp_final.choices[0].message.content = "Final Master Summary of Large PDF"

        mock_client.chat.completions.create.side_effect = [
            mock_resp_1,
            mock_resp_2,
            mock_resp_final
        ]

        # Mock count_tokens: large text is 15000 tokens, chunk summaries are 100 tokens
        def count_tokens_side_effect(text):
            if len(text) > 1000:
                return 15000
            return 100

        mock_count_tokens.side_effect = count_tokens_side_effect
        mock_chunk_text.return_value = [
            "Chunk 1 text content...",
            "Chunk 2 text content..."
        ]

        large_text = "Dummy large PDF text..."
        result = generate_summary(large_text, "medium")

        self.assertEqual(result, "Final Master Summary of Large PDF")
        # Groq client should be called 3 times (2 chunk calls + 1 reduce call)
        self.assertEqual(mock_client.chat.completions.create.call_count, 3)
        print("[Test Pass] Large PDF Map-Reduce multi-chunk flow executed correctly")

if __name__ == "__main__":
    unittest.main()
