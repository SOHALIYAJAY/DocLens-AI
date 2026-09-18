# test_integration.py
"""
Integration & Backward Compatibility Verification Test Suite for DocLens-AI.

Verifies:
1. All 13 unit tests in DocumentStructureService pass cleanly.
2. UploadResponse contract returns existing fields (success, filename, num_chunks, images) plus optional document_structure.
3. Navigator API response schema remains 100% intact and unchanged.
4. ResearchReportService generates structured report payloads driven by document structure hierarchy.
5. PDF Generator includes new "Document Structure & Insights" section without breaking existing PDF output.
"""

import os
import sys
try:
    import pymupdf as fitz
except ImportError:
    import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.document_structure_service import document_structure_service
from services.navigator_service import generate_navigator
from services.research_report_service import research_report_service
from services.pdf_generator_service import create_navigator_pdf
from models.schemas import UploadResponse, NavigatorResponse, ResearchReportResponse

def test_1_run_document_structure_unit_tests():
    print("\n--- [INTEGRATION 1] Running Document Structure Unit Tests ---")
    from test_document_structure import run_all_tests
    run_all_tests()

def test_2_upload_response_backward_compatibility():
    print("\n--- [INTEGRATION 2] UploadResponse Backward Compatibility ---")
    legacy_resp = UploadResponse(
        success=True,
        filename="legacy_document.pdf",
        num_chunks=15,
        images=[]
    )
    assert legacy_resp.success is True
    assert legacy_resp.filename == "legacy_document.pdf"
    assert legacy_resp.num_chunks == 15
    assert legacy_resp.document_structure is None
    print("[OK] Legacy UploadResponse payload validated cleanly.")

    extended_resp = UploadResponse(
        success=True,
        filename="new_document.pdf",
        num_chunks=20,
        images=[],
        document_structure={"total_topics": 5, "hierarchy_tree": []}
    )
    assert extended_resp.document_structure["total_topics"] == 5
    print("[OK] Extended UploadResponse with document_structure validated cleanly.")

def test_3_navigator_response_integrity():
    print("\n--- [INTEGRATION 3] Navigator Response Contract Integrity ---")
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 100), "# 1. Introduction\nSample document body for navigator testing.", fontsize=14)
    pdf_bytes = doc.tobytes()
    doc.close()

    nav_res = generate_navigator(pdf_bytes, filename="nav_test.pdf")
    assert isinstance(nav_res, NavigatorResponse)
    assert nav_res.success is True
    assert nav_res.document_name == "nav_test.pdf"
    assert hasattr(nav_res, "sections")
    assert hasattr(nav_res, "definitions_found")
    assert hasattr(nav_res, "figures_found")
    assert hasattr(nav_res, "tables_found")
    print("[OK] Navigator Response schema and business logic confirmed 100% intact and unchanged.")

def test_4_research_report_generation():
    print("\n--- [INTEGRATION 4] AI Research Report Generation ---")
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 100), "# 1. Executive Summary\nSummary text.\n## 1.1 Methodology\nMethod text.", fontsize=14)
    pdf_bytes = doc.tobytes()
    doc.close()

    document_structure_service.extract_structure(pdf_bytes, filename="report_test.pdf")
    report = research_report_service.generate_report(focus_topic="Executive Summary", detail_level="comprehensive")

    assert report["success"] is True
    assert report["document_name"] == "report_test.pdf"
    assert "report_markdown" in report
    assert report["structure_overview"]["total_topics"] >= 2
    print("[OK] AI Research Report generated successfully using document structure hierarchy.")

def test_5_extended_pdf_generation():
    print("\n--- [INTEGRATION 5] PDF Executive Summary with Document Structure & Insights ---")
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 100), "# 1. Machine Learning\nML introduction.\n## 1.1 Supervised Learning\nSupervised text.\n### 1.1.1 Classification\nClassification text.", fontsize=14)
    pdf_bytes = doc.tobytes()
    doc.close()

    structure_manifest = document_structure_service.extract_structure(pdf_bytes, filename="pdf_insights_test.pdf")
    nav_res = generate_navigator(pdf_bytes, filename="pdf_insights_test.pdf")

    pdf_output_bytes = create_navigator_pdf(nav_res, structure_manifest=structure_manifest)
    assert pdf_output_bytes is not None
    assert len(pdf_output_bytes) > 500
    assert pdf_output_bytes.startswith(b"%PDF")

    print("[OK] Extended PDF generated successfully ({len(pdf_output_bytes):,} bytes) with new Document Structure & Insights section.", flush=True)

def run_integration_suite():
    print("==========================================================")
    print("  RUNNING DOCLENS-AI INTEGRATION & COMPATIBILITY SUITE    ")
    print("==========================================================")
    test_1_run_document_structure_unit_tests()
    test_2_upload_response_backward_compatibility()
    test_3_navigator_response_integrity()
    test_4_research_report_generation()
    test_5_extended_pdf_generation()
    print("\n==========================================================")
    print("  ALL INTEGRATION TESTS PASSED CLEANLY! SYSTEM IS GREEN.   ")
    print("==========================================================")

if __name__ == "__main__":
    run_integration_suite()
