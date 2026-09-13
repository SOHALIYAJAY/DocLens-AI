# test_document_structure.py
"""
Comprehensive Unit Test Suite for DocumentStructureService in DocLens-AI.

Tests:
1. Numbered headings (1. Introduction, 2. Methods)
2. Nested numbered headings (1.1, 1.1.1, 2.3.4.1)
3. Unnumbered headings (# Abstract, ## Results)
4. Mixed heading formats (1. Intro, Methods, 2.1 Pipeline)
5. Missing hierarchy information (flat text lines)
6. Duplicate heading names (Overview in Ch1 and Overview in Ch2)
7. Headings spanning pages (Page 1 to Page 5 span)
8. Documents without a TOC
9. Documents with irregular numbering (1.0, 1.A, Appendix A, Section 3)
"""

import os
import sys
import fitz

# Ensure backend path is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.document_structure_service import document_structure_service

def test_1_numbered_headings():
    print("\n--- [TEST 1] Numbered Headings ---")
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 100), "1. Introduction\nThis is the intro text that provides sufficient length.", fontsize=12)
    p2 = doc.new_page()
    p2.insert_text((50, 100), "2. Methodology\nThis describes the methodology text in detail.", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    res = document_structure_service.extract_structure(pdf_bytes, filename="test_numbered.pdf")
    flat = res["flat_nodes"]
    assert res["success"] is True
    assert len(flat) >= 2, f"Expected 2 nodes, got {len(flat)}"
    assert flat[0]["level"] == 1
    assert "1. Introduction" in flat[0]["title"]
    print("[OK] Passed: Numbered headings extracted as Level 1 topics.")

def test_2_nested_numbered_headings():
    print("\n--- [TEST 2] Nested Numbered Headings ---")
    doc = fitz.open()
    p1 = doc.new_page()
    text = (
        "1. System Architecture\nArchitectural overview text.\n"
        "1.1 Backend Pipeline\nBackend service configuration.\n"
        "1.1.1 Data Ingestion\nIngestion details.\n"
        "2.3.4.1 Clause Specification\nDeep nested clause."
    )
    p1.insert_text((50, 100), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    res = document_structure_service.extract_structure(pdf_bytes, filename="test_nested.pdf")
    flat = res["flat_nodes"]
    assert len(flat) >= 4, f"Expected 4 nodes, got {len(flat)}"
    
    levels = [n["level"] for n in flat]
    assert levels[0] == 1, f"Expected L1, got {levels[0]}"
    assert levels[1] == 2, f"Expected L2, got {levels[1]}"
    assert levels[2] == 3, f"Expected L3, got {levels[2]}"
    assert levels[3] == 4, f"Expected L4, got {levels[3]}"

    # Parent relationship checks
    assert flat[1]["parent_id"] == flat[0]["node_id"]
    assert flat[2]["parent_id"] == flat[1]["node_id"]
    print("[OK] Passed: Nested numbered headings correctly assigned to Level 1, Level 2, Level 3, and Level 4 with parent links.")

def test_3_unnumbered_headings():
    print("\n--- [TEST 3] Unnumbered Headings (#, ##, ###) ---")
    doc = fitz.open()
    p1 = doc.new_page()
    text = (
        "# Executive Summary\nSummary text content.\n"
        "## Key Achievements\nAchievements details text.\n"
        "### Performance Benchmarks\nBenchmark metrics text."
    )
    p1.insert_text((50, 100), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    res = document_structure_service.extract_structure(pdf_bytes, filename="test_unnumbered.pdf")
    flat = res["flat_nodes"]
    assert len(flat) == 3
    assert flat[0]["level"] == 1 and flat[0]["title"] == "Executive Summary"
    assert flat[1]["level"] == 2 and flat[1]["title"] == "Key Achievements"
    assert flat[2]["level"] == 3 and flat[2]["title"] == "Performance Benchmarks"
    print("[OK] Passed: Unnumbered markdown headings (#, ##, ###) parsed cleanly.")

def test_4_mixed_heading_formats():
    print("\n--- [TEST 4] Mixed Heading Formats ---")
    doc = fitz.open()
    p1 = doc.new_page()
    text = (
        "# 1. Main Introduction\nOverview text.\n"
        "## Methods\nMethods text.\n"
        "2.1 Data Preprocessing\nPreprocessing text."
    )
    p1.insert_text((50, 100), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    res = document_structure_service.extract_structure(pdf_bytes, filename="test_mixed.pdf")
    flat = res["flat_nodes"]
    assert len(flat) == 3
    assert flat[0]["level"] == 1
    assert flat[1]["level"] == 2
    assert flat[2]["level"] == 2
    print("[OK] Passed: Mixed markdown and numbered heading formats parsed seamlessly.")

def test_5_missing_hierarchy_information():
    print("\n--- [TEST 5] Missing Hierarchy Information / Flat Text ---")
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 100), "Just plain body paragraph without any headers or structure indicators at all.", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    res = document_structure_service.extract_structure(pdf_bytes, filename="test_plain.pdf")
    assert res["success"] is True
    assert len(res["flat_nodes"]) >= 1
    assert res["flat_nodes"][0]["source"] in ("fallback", "typography", "font_size")
    print("[OK] Passed: Preserved default root structure for document lacking hierarchy signals without crashing.")

def test_6_duplicate_heading_names():
    print("\n--- [TEST 6] Duplicate Heading Names ---")
    doc = fitz.open()
    p1 = doc.new_page()
    text = (
        "1. Chapter One\nText 1.\n"
        "1.1 Overview\nOverview text 1.\n"
        "2. Chapter Two\nText 2.\n"
        "2.1 Overview\nOverview text 2."
    )
    p1.insert_text((50, 100), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    res = document_structure_service.extract_structure(pdf_bytes, filename="test_duplicates.pdf")
    flat = res["flat_nodes"]
    assert len(flat) == 4
    
    # Verify node IDs are unique
    node_ids = set(n["node_id"] for n in flat)
    assert len(node_ids) == 4, "Node IDs must be unique even with duplicate titles"
    
    # Verify parent titles differ
    assert flat[1]["relationships"]["parent_title"] == "1. Chapter One"
    assert flat[3]["relationships"]["parent_title"] == "2. Chapter Two"
    print("[OK] Passed: Duplicate heading names maintain unique node IDs and distinct parent mappings.")

def test_7_headings_spanning_pages():
    print("\n--- [TEST 7] Headings Spanning Pages ---")
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 100), "1. Section One\nText on page 1.", fontsize=12)
    doc.new_page().insert_text((50, 100), "Continued text on page 2.", fontsize=12)
    doc.new_page().insert_text((50, 100), "Continued text on page 3.", fontsize=12)
    p4 = doc.new_page()
    p4.insert_text((50, 100), "2. Section Two\nText on page 4.", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    res = document_structure_service.extract_structure(pdf_bytes, filename="test_spans.pdf")
    flat = res["flat_nodes"]
    assert len(flat) == 2
    sec1 = flat[0]
    assert sec1["page_start"] == 1
    assert sec1["page_end"] == 4
    assert sec1["relationships"]["page_span"] == "Pages 1-4"
    print("[OK] Passed: Page spans accurately calculated across multi-page sections.")

def test_8_documents_without_toc():
    print("\n--- [TEST 8] Documents Without a TOC ---")
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 100), "# 1. Introduction\nIntro text without TOC.", fontsize=12)
    pdf_bytes = doc.tobytes()
    
    # Ensure TOC is empty
    check_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert len(check_doc.get_toc()) == 0
    check_doc.close()

    res = document_structure_service.extract_structure(pdf_bytes, filename="test_no_toc.pdf")
    assert res["success"] is True
    assert len(res["flat_nodes"]) >= 1
    print("[OK] Passed: Document without native TOC parsed structure correctly via parser signals.")

def test_9_irregular_numbering():
    print("\n--- [TEST 9] Irregular Numbering (1.0, 1.A, Appendix A, Section 3) ---")
    doc = fitz.open()
    p1 = doc.new_page()
    text = (
        "Section 1 Overview\nSection 1 text.\n"
        "1.0 Main System\nMain system text.\n"
        "1.A Sub-clause Alpha\nAlpha text.\n"
        "Appendix A Supplementary Data\nAppendix text."
    )
    p1.insert_text((50, 100), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    res = document_structure_service.extract_structure(pdf_bytes, filename="test_irregular.pdf")
    flat = res["flat_nodes"]
    assert len(flat) >= 3
    print("[OK] Passed: Irregular numbering formats (1.0, 1.A, Appendix A, Section X) handled successfully.")

def run_all_tests():
    print("==========================================================")
    print("  RUNNING DOCUMENT STRUCTURE HIERARCHY UNIT TEST SUITE    ")
    print("==========================================================")
    test_1_numbered_headings()
    test_2_nested_numbered_headings()
    test_3_unnumbered_headings()
    test_4_mixed_heading_formats()
    test_5_missing_hierarchy_information()
    test_6_duplicate_heading_names()
    test_7_headings_spanning_pages()
    test_8_documents_without_toc()
    test_9_irregular_numbering()
    print("\n==========================================================")
    print("  ALL 9 UNIT TESTS PASSED CLEANLY WITH ZERO ERRORS!      ")
    print("==========================================================")

if __name__ == "__main__":
    run_all_tests()
