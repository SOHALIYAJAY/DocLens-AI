# test_comprehensive_system.py
import unittest
from unittest.mock import MagicMock, patch
import os
import groq

from services.token_service import count_tokens
from services.chunk_service import chunk_text_by_tokens
from services.rate_limiter_service import TokenRateLimiter
from services.llm_service import (
    generate_summary,
    execute_groq_completion_with_retry,
    reduce_summaries_hierarchically
)

class TestComprehensiveLargePDFSummarizationSystem(unittest.TestCase):

    def setUp(self):
        from services.rate_limiter_service import groq_rate_limiter
        groq_rate_limiter.history.clear()
        groq_rate_limiter.max_tpm = 1000000

        self.paragraph = (
            "Section {sec}: Artificial intelligence and machine learning are revolutionizing automated PDF processing. "
            "Model performance achieved 98.4% accuracy across 15,000 benchmark documents evaluated in Q3 2026. "
            "Methodology involved multi-stage RAG retrieval paired with hierarchical summarization pipelines. "
            "However, key limitations include rate limits on public API endpoints and memory constraints.\n\n"
        )

    # ---------------------------------------------------------
    # Case 1: Small PDF
    # ---------------------------------------------------------
    @patch("services.llm_service.get_groq_client")
    def test_case_1_small_pdf(self, mock_get_client):
        """1. Small PDF (<6500 tokens): Single-pass summarization without chunking overhead."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Small PDF Concise Summary"
        mock_client.chat.completions.create.return_value = mock_response

        small_text = "".join([self.paragraph.format(sec=i) for i in range(1, 5)])
        tokens = count_tokens(small_text)
        self.assertLess(tokens, 6500)

        result = generate_summary(small_text, "small")

        self.assertEqual(result, "Small PDF Concise Summary")
        self.assertEqual(mock_client.chat.completions.create.call_count, 1)
        print(f"\n[Case 1 Pass] Small PDF ({tokens} tokens) processed via single-pass flow")

    # ---------------------------------------------------------
    # Case 2: Medium PDF
    # ---------------------------------------------------------
    @patch("services.llm_service.get_groq_client")
    def test_case_2_medium_pdf(self, mock_get_client):
        """2. Medium PDF (~15,000 tokens): Map-Reduce flow with overlap and single flat reduction."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock responses: 3 chunk summaries + 1 final summary
        res_chunk1 = MagicMock()
        res_chunk1.choices[0].message.content = "Summary of Chunk 1: Intro & AI metrics (98.4%)."
        res_chunk2 = MagicMock()
        res_chunk2.choices[0].message.content = "Summary of Chunk 2: RAG methodology."
        res_chunk3 = MagicMock()
        res_chunk3.choices[0].message.content = "Summary of Chunk 3: Limitations & future work."
        res_final = MagicMock()
        res_final.choices[0].message.content = "Final Medium PDF Summary"

        mock_client.chat.completions.create.side_effect = [
            res_chunk1, res_chunk2, res_chunk3, res_final
        ]

        # Generate ~15,000 tokens of text
        medium_text = "".join([self.paragraph.format(sec=i) for i in range(1, 260)])
        tokens = count_tokens(medium_text)
        self.assertGreater(tokens, 10000)

        chunks = chunk_text_by_tokens(medium_text, max_tokens_per_chunk=6500, overlap_tokens=400)
        self.assertGreater(len(chunks), 1)

        # Verify chunk overlap between chunk 0 and chunk 1
        end_chunk_0 = chunks[0][-100:]
        self.assertIn(end_chunk_0[:40], chunks[1])

        result = generate_summary(medium_text, "medium")

        self.assertEqual(result, "Final Medium PDF Summary")
        self.assertEqual(mock_client.chat.completions.create.call_count, len(chunks) + 1)
        print(f"[Case 2 Pass] Medium PDF ({tokens} tokens, {len(chunks)} chunks) processed with overlap and flat reduction")

    # ---------------------------------------------------------
    # Case 3: Large PDF
    # ---------------------------------------------------------
    @patch("services.rate_limiter_service.groq_rate_limiter.wait_for_capacity")
    @patch("services.llm_service.get_groq_client")
    def test_case_3_large_pdf(self, mock_get_client, mock_rate_limit_wait):
        """3. Large PDF (~40,000 tokens): Order preservation & TPM rate limit checks."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Return mock summary for all chunk & final calls
        def mock_create(**kwargs):
            resp = MagicMock()
            resp.choices[0].message.content = "Section summary content..."
            return resp
            
        mock_client.chat.completions.create.side_effect = mock_create

        large_text = "".join([self.paragraph.format(sec=i) for i in range(1, 600)])
        tokens = count_tokens(large_text)

        chunks = chunk_text_by_tokens(large_text, max_tokens_per_chunk=6500, overlap_tokens=400)
        self.assertGreaterEqual(len(chunks), 4)

        # Verify chunk ordering: First section ID in each chunk must ascend strictly across chunks
        import re
        first_sec_ids = []
        for chunk in chunks:
            sec_ids = [int(x) for x in re.findall(r"Section (\d+):", chunk)]
            if sec_ids:
                if first_sec_ids:
                    self.assertGreater(sec_ids[0], first_sec_ids[-1])
                first_sec_ids.append(sec_ids[0])

        result = generate_summary(large_text, "large")
        self.assertTrue(bool(result))
        self.assertGreaterEqual(mock_rate_limit_wait.call_count, len(chunks) + 1)
        print(f"[Case 3 Pass] Large PDF ({tokens} tokens, {len(chunks)} chunks) verified for strict section order preservation & TPM checks")

    # ---------------------------------------------------------
    # Case 4: Very Large PDF (Hierarchical Summarization)
    # ---------------------------------------------------------
    @patch("services.llm_service.execute_groq_completion_with_retry")
    def test_case_4_very_large_pdf_hierarchical(self, mock_execute_retry):
        """4. Very Large PDF: Multi-level hierarchical reduction tree when combined chunk summaries exceed token limit."""
        mock_final = MagicMock()
        mock_final.choices[0].message.content = "Final Master Hierarchical Summary"

        call_counter = 0
        def dynamic_mock(client, model, max_tokens, temperature, messages):
            nonlocal call_counter
            call_counter += 1
            user_msg = messages[1]["content"]
            if "group_summaries" in user_msg:
                inter_resp = MagicMock()
                inter_resp.choices[0].message.content = f"Intermediate Group Summary {call_counter}"
                return inter_resp
            return mock_final

        mock_execute_retry.side_effect = dynamic_mock

        # 12 large chunk summaries
        summaries = [f"Section {i} Summary: " + ("Extensive findings details. " * 30) for i in range(1, 13)]

        result = reduce_summaries_hierarchically(
            summaries=summaries,
            summary_type="large",
            system_instruction="System instruction...",
            client=MagicMock(),
            model_name="groq/compound",
            max_reduce_tokens=600  # low limit to trigger hierarchical grouping
        )

        self.assertEqual(result, "Final Master Hierarchical Summary")
        self.assertGreater(mock_execute_retry.call_count, 1)
        print(f"[Case 4 Pass] Very Large PDF hierarchical reduction tree executed ({mock_execute_retry.call_count} API calls)")

    # ---------------------------------------------------------
    # Case 5: Empty PDF
    # ---------------------------------------------------------
    def test_case_5_empty_pdf(self):
        """5. Empty PDF: Validates empty input handling raises ValueError immediately without API calls."""
        with self.assertRaises(ValueError) as cm:
            generate_summary("", "medium")
        self.assertIn("empty", str(cm.exception).lower())

        with self.assertRaises(ValueError) as cm2:
            generate_summary("   \n\t  ", "medium")
        self.assertIn("empty", str(cm2.exception).lower())

        print("[Case 5 Pass] Empty PDF input validation verified")

    # ---------------------------------------------------------
    # Case 6: PDF with Very Long Sections
    # ---------------------------------------------------------
    def test_case_6_very_long_sections(self):
        """6. Very Long Sections: Verifies unbroken text/paragraphs break safely without overflow."""
        very_long_paragraph = "Word " * 15000  # ~15,000 continuous tokens without headings or double linebreaks
        tokens = count_tokens(very_long_paragraph)

        chunks = chunk_text_by_tokens(very_long_paragraph, max_tokens_per_chunk=6500, overlap_tokens=400)
        self.assertGreater(len(chunks), 1)

        for idx, chunk in enumerate(chunks):
            c_tokens = count_tokens(chunk)
            self.assertLessEqual(c_tokens, 6600)  # boundary tolerance

        print(f"[Case 6 Pass] Very long section ({tokens} tokens) safely split into {len(chunks)} valid chunks")

    # ---------------------------------------------------------
    # Case 7: Simulated Groq 429 Rate Limit Response & Retry Handling
    # ---------------------------------------------------------
    @patch("time.sleep")
    def test_case_7_groq_429_retry_handling(self, mock_sleep):
        """7. Groq 429 Retry Handling: Simulates 429 response, reads wait time, retries, and succeeds."""
        mock_client = MagicMock()
        mock_success = MagicMock()
        mock_success.choices[0].message.content = "Summary generated after 429 retry"

        # Mock 429 error on 1st call, success on 2nd call
        err_429 = groq.RateLimitError(
            message="Rate limit reached. Please try again in 1.5s",
            response=MagicMock(headers={"retry-after": "1.5"}),
            body=None
        )
        mock_client.chat.completions.create.side_effect = [err_429, mock_success]

        response = execute_groq_completion_with_retry(mock_client, model="groq/compound")

        self.assertEqual(response.choices[0].message.content, "Summary generated after 429 retry")
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)
        mock_sleep.assert_called_once()
        print("[Case 7 Pass] Simulated Groq 429 response handled with automatic retry & recovery")

if __name__ == "__main__":
    unittest.main()
