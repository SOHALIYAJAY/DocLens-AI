# test_hierarchical_summarization.py
import unittest
from unittest.mock import MagicMock, patch
from services.llm_service import reduce_summaries_hierarchically

class TestHierarchicalSummarization(unittest.TestCase):

    @patch("services.llm_service.execute_groq_completion_with_retry")
    def test_1_flat_reduction_when_under_token_limit(self, mock_execute_retry):
        """1. When combined token size is under limit, performs direct 1-step final reduction."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Final Master Summary from 3 small section summaries."
        mock_execute_retry.return_value = mock_response

        summaries = [
            "Section 1 summary: Introduces AI document processing concepts.",
            "Section 2 summary: Details vector embeddings and RAG retrieval.",
            "Section 3 summary: Explains LLM token optimization strategies."
        ]

        result = reduce_summaries_hierarchically(
            summaries=summaries,
            summary_type="medium",
            system_instruction="System prompt instruction...",
            client=MagicMock(),
            model_name="groq/compound",
            max_reduce_tokens=6000
        )

        self.assertEqual(result, "Final Master Summary from 3 small section summaries.")
        # Under limit -> exactly 1 final Groq call
        self.assertEqual(mock_execute_retry.call_count, 1)
        print("\n[Test Pass] Flat reduction under token limit executed correctly")

    @patch("services.llm_service.execute_groq_completion_with_retry")
    def test_2_hierarchical_intermediate_grouping_when_over_limit(self, mock_execute_retry):
        """2. When combined token size exceeds max_reduce_tokens, creates intermediate groups before final reduction."""
        mock_final = MagicMock()
        mock_final.choices[0].message.content = "Hierarchical Master Summary for Huge Document"

        call_counter = 0
        def dynamic_mock_execute(client, model, max_tokens, temperature, messages):
            nonlocal call_counter
            call_counter += 1
            user_msg = messages[1]["content"]
            if "group_summaries" in user_msg:
                inter_resp = MagicMock()
                inter_resp.choices[0].message.content = f"Intermediate Summary {call_counter}"
                return inter_resp
            return mock_final

        mock_execute_retry.side_effect = dynamic_mock_execute

        # Generate 10 large mock summaries
        large_summary_item = "Key concept: " + ("Detailed analysis of document section with extensive explanation. " * 30)
        large_summaries = [f"Section {i}: {large_summary_item}" for i in range(1, 11)]

        # Set max_reduce_tokens=800 to force multiple intermediate groups
        result = reduce_summaries_hierarchically(
            summaries=large_summaries,
            summary_type="large",
            system_instruction="System prompt instruction...",
            client=MagicMock(),
            model_name="groq/compound",
            max_reduce_tokens=800
        )

        self.assertEqual(result, "Hierarchical Master Summary for Huge Document")
        # Should have made multiple calls (intermediate groups + final call)
        self.assertGreater(mock_execute_retry.call_count, 1)
        print(f"[Test Pass] Hierarchical grouping and reduction executed correctly ({mock_execute_retry.call_count} API calls)")

if __name__ == "__main__":
    unittest.main()
