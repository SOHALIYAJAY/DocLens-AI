# test_step13_regression_suite.py
"""
Step 13: Consolidated Regression Test Suite for DocLens-AI RAG Chatbot.
Runs all previous unit/integration tests alongside new Step 13 evaluation tests.
Prints consolidated totals for previous tests, new evaluation tests, total passed, and total failed.
"""

import unittest
import sys

from test_comprehensive_citations import TestPDFMetadataCitations
from test_comprehensive_grounding import TestGroundingAndHallucinationProtection
from test_comprehensive_figures import TestFigureDiagramChartUnderstanding
from test_comprehensive_conversational_and_tables import TestConversationalAndTableHandling
from test_comprehensive_system import TestComprehensiveLargePDFSummarizationSystem
from test_topic_service import TestTopicService

# Import benchmark loader
import json
import os
from run_step13_benchmark import seed_step13_knowledge_base, config_e_final_pipeline, BENCHMARK_PATH

class TestStep13NewEvaluationRegressions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        seed_step13_knowledge_base()
        with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
            cls.dataset = json.load(f)

    def clean_text(self, text: str) -> str:
        return text.replace("\u202f", "").replace("\u00a0", "").replace(" ", "").lower()

    def test_r1_multiturn_conversational_context(self):
        """Regression Test 1: Multi-turn conversational sequence context preservation."""
        item1 = next(i for i in self.dataset if i["id"] == 26)
        out1 = config_e_final_pipeline(item1)
        self.assertIn("8.5m", self.clean_text(out1["answer"]))
        self.assertIn("Table 1 — Page 3", out1["answer"])

    def test_r2_hallucination_protection_non_existent(self):
        """Regression Test 2: Non-existent question returns exact safe response without inventing information."""
        item2 = next(i for i in self.dataset if i["id"] == 44)
        out2 = config_e_final_pipeline(item2)
        self.assertIn("couldn't find enough information", out2["answer"].lower())

    def test_r3_table_deterministic_math(self):
        """Regression Test 3: Table YoY calculation achieves exact deterministic precision (+41.18%)."""
        item3 = next(i for i in self.dataset if i["id"] == 32)
        out3 = config_e_final_pipeline(item3)
        self.assertIn("41.18", self.clean_text(out3["answer"]))

    def test_r4_figure_diagram_citation(self):
        """Regression Test 4: Figure 4 query cites Page 4 and Figure 4 deterministically."""
        item4 = next(i for i in self.dataset if i["id"] == 35)
        out4 = config_e_final_pipeline(item4)
        self.assertIn("Figure 4", out4["answer"])
        self.assertIn("Page 4", out4["answer"])

    def test_r5_long_pdf_page32_retrieval(self):
        """Regression Test 5: Long PDF (Page 32) SLA retrieval matches Page 32 metadata."""
        item5 = next(i for i in self.dataset if i["id"] == 50)
        out5 = config_e_final_pipeline(item5)
        self.assertIn("99.9", self.clean_text(out5["answer"]))
        self.assertIn("Page 32", out5["answer"])

    def test_r6_topic_count_and_structure_awareness(self):
        """Regression Test 6: 'how many topic is exist' query returns exact topic count and grounded list."""
        topic_item = {
            "id": 999,
            "question": "how many topic is exist",
            "history": []
        }
        out = config_e_final_pipeline(topic_item)
        self.assertTrue(any(digit in out["answer"] for digit in ["9", "nine"]), "Topic count should state 9 topics.")
        self.assertIn("introduction", out["answer"].lower())
        self.assertTrue(len(out["sources"]) >= 1, "Should include structured citations for topics.")


def run_consolidated_suite():
    print("========== RUNNING CONSOLIDATED REGRESSION TEST SUITE ==========\n")

    suite = unittest.TestSuite()
    
    # Add previous test classes (34 tests)
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestPDFMetadataCitations))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestGroundingAndHallucinationProtection))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestFigureDiagramChartUnderstanding))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestConversationalAndTableHandling))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestComprehensiveLargePDFSummarizationSystem))
    
    # Add Topic Service unit/integration tests (5 tests)
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestTopicService))

    # Add Step 13 evaluation regression tests (6 tests)
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestStep13NewEvaluationRegressions))

    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    prev_test_count = 34
    topic_test_count = 5
    eval_test_count = 6
    total_tests = result.testsRun
    failures = len(result.failures) + len(result.errors)
    passed = total_tests - failures

    print("\n=======================================================================")
    print("                CONSOLIDATED TEST SUITE SUMMARY RESULTS                ")
    print("=======================================================================")
    print(f"Previous System Tests:     {prev_test_count}")
    print(f"Topic Service Tests:       {topic_test_count}")
    print(f"Step 13 Evaluation Tests:  {eval_test_count}")
    print(f"Total Tests Executed:     {total_tests}")
    print(f"Total Passed:             {passed}")
    print(f"Total Failed:             {failures}")
    print(f"Overall Success Rate:     {(passed / total_tests) * 100:.1f}%\n")

if __name__ == "__main__":
    run_consolidated_suite()
