# test_comprehensive_grounding.py
import unittest
from unittest.mock import patch, MagicMock
import sys

from services.grounding_service import (
    verify_grounding,
    generate_grounded_response,
    check_numeric_grounding,
    INSUFFICIENT_EVIDENCE_RESPONSE
)

class TestGroundingAndHallucinationProtection(unittest.TestCase):

    def setUp(self):
        self.context_chunks = [
            "[Page 1] [Section: Financial Results]\nCompany revenue in 2024 reached $12.0M, representing a 41.18% increase compared to 2023 revenue of $8.5M.",
            "[Page 2] [Section: Operations]\nTotal operating expenses in 2024 were $9.5M, leaving a net profit of $2.5M."
        ]

    # =========================================================================
    # GROUNDING & HALLUCINATION PROTECTION TESTS (6 Test Cases)
    # =========================================================================

    @patch("services.grounding_service.verify_grounding")
    @patch("services.grounding_service.default_llm_generate")
    def test_1_answer_exists(self, mock_generate, mock_verify):
        """1. Answer Exists: Complete evidence in PDF context; verifier outputs PASS."""
        mock_generate.return_value = "In 2024, the company's revenue reached $12.0M, up 41.18% from $8.5M in 2023 [Page 1]."
        mock_verify.return_value = {
            "supported_by_evidence": True,
            "factual_claims_supported": True,
            "numbers_supported": True,
            "dates_supported": True,
            "citations_supported": True,
            "contains_invented_info": False,
            "verdict": "PASS",
            "feedback": ""
        }

        ans = generate_grounded_response(self.context_chunks, "What was the company's revenue in 2024?")
        self.assertIn("$12.0M", ans)
        self.assertNotEqual(ans, INSUFFICIENT_EVIDENCE_RESPONSE)
        print(f"\n[Test 1 Pass] Answer Exists verified: '{ans}'")

    @patch("services.grounding_service.verify_grounding")
    @patch("services.grounding_service.default_llm_generate")
    def test_2_answer_partially_exists(self, mock_generate, mock_verify):
        """2. Answer Partially Exists: Partial evidence; verifier flags ungrounded claim and triggers 1 retry."""
        # Attempt 1: hallucinated dividend claim -> FAIL
        # Attempt 2: grounded answer -> PASS
        mock_generate.side_effect = [
            "Revenue was $12.0M and dividend payout was $5.0M.",
            "Revenue was $12.0M in 2024 [Page 1]."
        ]
        mock_verify.side_effect = [
            {
                "supported_by_evidence": False,
                "factual_claims_supported": False,
                "numbers_supported": False,
                "dates_supported": True,
                "citations_supported": True,
                "contains_invented_info": True,
                "verdict": "FAIL",
                "feedback": "Dividend payout of $5.0M is not mentioned in evidence."
            },
            {
                "supported_by_evidence": True,
                "factual_claims_supported": True,
                "numbers_supported": True,
                "dates_supported": True,
                "citations_supported": True,
                "contains_invented_info": False,
                "verdict": "PASS",
                "feedback": ""
            }
        ]

        ans = generate_grounded_response(self.context_chunks, "What was revenue and dividend payout in 2024?")
        self.assertIn("Revenue was $12.0M", ans)
        self.assertNotIn("dividend", ans.lower())
        self.assertEqual(mock_generate.call_count, 2)  # MAX_VERIFICATION_RETRIES = 1 retry executed
        print(f"[Test 2 Pass] Answer Partially Exists corrected via 1 retry: '{ans}'")

    def test_3_answer_does_not_exist(self):
        """3. Answer Does Not Exist: Topic unmentioned in PDF context; returns standard fallback string."""
        empty_context = ["The document discusses basic accounting principles."]
        q = "What is the quantum computing algorithm used?"
        
        # When context is insufficient, returns exact standard response string
        ans = generate_grounded_response(empty_context, q)
        self.assertEqual(ans, INSUFFICIENT_EVIDENCE_RESPONSE)
        print(f"[Test 3 Pass] Answer Does Not Exist returns standard fallback: '{ans}'")

    @patch("services.grounding_service.verify_grounding")
    @patch("services.grounding_service.default_llm_generate")
    def test_4_misleading_question(self, mock_generate, mock_verify):
        """4. Misleading Question: False premise in question ('Why did revenue drop by 90%?'); verifier blocks hallucinated answer."""
        mock_generate.return_value = "Revenue dropped by 90% due to market downturns."
        mock_verify.return_value = {
            "supported_by_evidence": False,
            "factual_claims_supported": False,
            "numbers_supported": False,
            "dates_supported": True,
            "citations_supported": False,
            "contains_invented_info": True,
            "verdict": "FAIL",
            "feedback": "Revenue did not drop by 90%; context states revenue grew to $12.0M."
        }

        ans = generate_grounded_response(self.context_chunks, "Why did revenue drop by 90% in 2024?")
        self.assertEqual(ans, INSUFFICIENT_EVIDENCE_RESPONSE)
        print(f"[Test 4 Pass] Misleading Question false premise blocked: '{ans}'")

    def test_5_numerical_question(self):
        """5. Numerical Question: Deterministic numeric check catches invented numbers not in context."""
        context_str = "Revenue in 2024 was $12.0M."
        
        # Valid number in context -> True
        self.assertTrue(check_numeric_grounding("Revenue was $12.0M in 2024.", context_str))
        
        # Invented number ($99.9M) not in context -> False
        self.assertFalse(check_numeric_grounding("Revenue reached $99.9M in 2024.", context_str))
        print("[Test 5 Pass] Numerical Question deterministic pre-check verified")

    @patch("services.grounding_service.verify_grounding")
    @patch("services.grounding_service.default_llm_generate")
    def test_6_multisource_answer(self, mock_generate, mock_verify):
        """6. Multi-Source Answer: Synthesizes evidence across Page 1 (revenue) and Page 2 (expenses)."""
        mock_generate.return_value = "In 2024, revenue was $12.0M [Page 1] and operating expenses were $9.5M [Page 2], resulting in $2.5M net profit."
        mock_verify.return_value = {
            "supported_by_evidence": True,
            "factual_claims_supported": True,
            "numbers_supported": True,
            "dates_supported": True,
            "citations_supported": True,
            "contains_invented_info": False,
            "verdict": "PASS",
            "feedback": ""
        }

        ans = generate_grounded_response(self.context_chunks, "Give a summary of 2024 financial performance.")
        self.assertIn("$12.0M", ans)
        self.assertIn("$9.5M", ans)
        self.assertNotEqual(ans, INSUFFICIENT_EVIDENCE_RESPONSE)
        print(f"[Test 6 Pass] Multi-Source Answer synthesized and grounded: '{ans}'")

if __name__ == "__main__":
    unittest.main()
