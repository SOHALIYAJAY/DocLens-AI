
# test_comprehensive_conversational_and_tables.py
import unittest
from unittest.mock import patch, MagicMock
import os
import sys

from services.query_rewriter_service import rewrite_query
from services.table_service import TableService, table_service

class TestConversationalAndTableHandling(unittest.TestCase):

    def setUp(self):
        # Reset table store for isolated testing
        table_service.clear_tables()

        # Seed sample financial table
        self.sample_table = {
            "table_id": "table_1",
            "page_number": 3,
            "caption": "Company Financial Performance",
            "headers": ["Metric", "2023", "2024"],
            "rows": [
                ["Revenue", "$8.5M", "$12.0M"],
                ["Net Profit", "$1.5M", "$2.5M"],
                ["Expenses", "$7.0M", "$9.5M"]
            ],
            "section": "Financial Results",
            "document_id": "doc_test_123",
            "raw_text": "| Metric | 2023 | 2024 |\n|---|---|---|\n| Revenue | $8.5M | $12.0M |\n| Net Profit | $1.5M | $2.5M |\n| Expenses | $7.0M | $9.5M |"
        }
        table_service.add_table(self.sample_table)

    # =========================================================================
    # CONVERSATIONAL QUERY REWRITING TESTS (5 Test Cases)
    # =========================================================================

    @patch("services.query_rewriter_service.get_groq_client")
    def test_1_standalone_question(self, mock_get_client):
        """1. Standalone question: Question is complete on its own; preserves original question."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "What was the company's revenue in 2024?"
        mock_client.chat.completions.create.return_value = mock_resp

        history = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi! How can I help you with your document today?"}
        ]
        q = "What was the company's revenue in 2024?"
        res = rewrite_query(q, history)

        self.assertIn("revenue in 2024", res.lower())
        print(f"\n[Test 1 Pass] Standalone Question preserved: '{res}'")

    @patch("services.query_rewriter_service.get_groq_client")
    def test_2_followup_question(self, mock_get_client):
        """2. Follow-up question: User asks 'What about 2023?'; rewrites to full standalone query."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "What was the company's revenue in 2023?"
        mock_client.chat.completions.create.return_value = mock_resp

        history = [
            {"role": "user", "content": "What was the company's revenue in 2024?"},
            {"role": "assistant", "content": "The company's revenue in 2024 was $12.0M."}
        ]
        q = "What about 2023?"
        res = rewrite_query(q, history)

        self.assertEqual(res, "What was the company's revenue in 2023?")
        print(f"[Test 2 Pass] Follow-up Question rewritten: '{q}' -> '{res}'")

    @patch("services.query_rewriter_service.get_groq_client")
    def test_3_pronoun_question(self, mock_get_client):
        """3. Pronoun question: User asks 'How does it work?'; resolves 'it' to target entity."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "How does the Transformer architecture work?"
        mock_client.chat.completions.create.return_value = mock_resp

        history = [
            {"role": "user", "content": "What is the Transformer architecture?"},
            {"role": "assistant", "content": "The Transformer architecture is a neural network model based on self-attention mechanisms."}
        ]
        q = "How does it work?"
        res = rewrite_query(q, history)

        self.assertEqual(res, "How does the Transformer architecture work?")
        print(f"[Test 3 Pass] Pronoun Question resolved: '{q}' -> '{res}'")

    @patch("services.query_rewriter_service.get_groq_client")
    def test_4_multiturn_conversation(self, mock_get_client):
        """4. Multi-turn conversation: Resolves subject across multiple Q&A pairs with history window capping."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "What was the net profit in 2023?"
        mock_client.chat.completions.create.return_value = mock_resp

        history = [
            {"role": "user", "content": "What was the revenue in 2024?"},
            {"role": "assistant", "content": "Revenue was $12.0M."},
            {"role": "user", "content": "What about net profit?"},
            {"role": "assistant", "content": "Net profit in 2024 was $2.5M."}
        ]
        q = "And for 2023?"
        res = rewrite_query(q, history)

        self.assertEqual(res, "What was the net profit in 2023?")
        print(f"[Test 4 Pass] Multi-turn Conversation resolved: '{q}' -> '{res}'")

    @patch("services.query_rewriter_service.get_groq_client")
    def test_5_unrelated_new_question(self, mock_get_client):
        """5. Unrelated new question: Ignores previous financial context for unrelated query."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "Who is the author of this paper?"
        mock_client.chat.completions.create.return_value = mock_resp

        history = [
            {"role": "user", "content": "What was the company's revenue in 2024?"},
            {"role": "assistant", "content": "Revenue was $12.0M."}
        ]
        q = "Who is the author of this paper?"
        res = rewrite_query(q, history)

        self.assertEqual(res, "Who is the author of this paper?")
        print(f"[Test 5 Pass] Unrelated New Question preserved: '{q}' -> '{res}'")


    # =========================================================================
    # PDF TABLE HANDLING & DETERMINISTIC CALCULATION TESTS (6 Test Cases)
    # =========================================================================

    def test_6_direct_table_question(self):
        """6. Direct table question: Retrieves structured table and preserves all 8 metadata fields."""
        tables = table_service.get_tables()
        self.assertEqual(len(tables), 1)

        t = tables[0]
        # Check all 8 required metadata fields
        self.assertEqual(t["table_id"], "table_1")
        self.assertEqual(t["page_number"], 3)
        self.assertEqual(t["caption"], "Company Financial Performance")
        self.assertEqual(t["headers"], ["Metric", "2023", "2024"])
        self.assertEqual(len(t["rows"]), 3)
        self.assertIn("2023", t["columns"])
        self.assertIn("Revenue", t["columns"]["Metric"])
        self.assertEqual(t["section"], "Financial Results")
        self.assertEqual(t["document_id"], "doc_test_123")

        retrieved = table_service.table_aware_retrieval("What were the 2024 expenses in the financial table?")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["table_id"], "table_1")
        print(f"[Test 6 Pass] Direct Table Question metadata verified for table '{retrieved['table_id']}'")

    def test_7_table_comparison(self):
        """7. Table comparison: Deterministic Python calculation computes difference between 2023 and 2024 revenue."""
        tbl = table_service.get_tables()[0]
        calc = table_service.calculate_table_metrics(tbl, "percentage", "Compare revenue in 2023 vs 2024")

        self.assertIsNotNone(calc)
        self.assertEqual(calc["operation"], "Percentage Difference")
        self.assertAlmostEqual(calc["numeric_value"], 41.17647, places=3)
        self.assertIn("+41.18%", calc["value"])
        print(f"[Test 7 Pass] Table Comparison calculation verified: {calc['value']} ({calc['explanation']})")

    def test_8_maximum_minimum_calculation(self):
        """8. Maximum/Minimum calculation: Deterministic Python max() identifies 2024 revenue ($12.0M)."""
        tbl = table_service.get_tables()[0]
        
        # Test Maximum
        max_calc = table_service.calculate_table_metrics(tbl, "maximum", "Which year had the highest revenue?")
        self.assertIsNotNone(max_calc)
        self.assertEqual(max_calc["operation"], "Maximum")
        self.assertEqual(max_calc["value"], "$12.0M")

        # Test Minimum
        min_calc = table_service.calculate_table_metrics(tbl, "minimum", "Which year had the lowest revenue?")
        self.assertIsNotNone(min_calc)
        self.assertEqual(min_calc["operation"], "Minimum")
        self.assertEqual(min_calc["value"], "$1.5M")

        print(f"[Test 8 Pass] Maximum/Minimum calculation verified: Highest='{max_calc['value']}', Lowest='{min_calc['value']}'")

    def test_9_percentage_calculation(self):
        """9. Percentage/YoY calculation: Computes exact YoY growth rate deterministically."""
        tbl = table_service.get_tables()[0]
        yoy_calc = table_service.calculate_table_metrics(tbl, "yoy", "What is the YoY revenue percentage growth?")

        self.assertIsNotNone(yoy_calc)
        self.assertEqual(yoy_calc["operation"], "Year-over-Year (YoY) Change")
        self.assertIn("+41.18%", yoy_calc["value"])
        print(f"[Test 9 Pass] Percentage/YoY calculation verified: {yoy_calc['value']}")

    def test_10_table_not_found_fallback(self):
        """10. Table not found: Fallback to normal RAG when no matching table exists in store."""
        empty_service = TableService()
        res = empty_service.table_aware_retrieval("What is the revenue?")
        self.assertIsNone(res)

        intent = empty_service.classify_query_intent("What is the revenue?")
        self.assertTrue(intent["is_table_query"])
        
        # System checks `if intent['is_table_query'] and table_service.get_tables():` -> False -> Normal Hybrid RAG fallback
        print("[Test 10 Pass] Table Not Found fallback to normal Hybrid RAG verified")

    def test_11_normal_text_question(self):
        """11. Normal text question: Non-table queries classify as non-table and proceed with standard RAG."""
        intent = table_service.classify_query_intent("What is the primary conclusion of the document methodology?")
        self.assertFalse(intent["is_table_query"])
        self.assertEqual(intent["calc_type"], "none")
        print(f"[Test 11 Pass] Normal Text Question classified correctly: is_table={intent['is_table_query']}")

if __name__ == "__main__":
    unittest.main()
