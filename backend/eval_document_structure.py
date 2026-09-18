# eval_document_structure.py
"""
Automated Evaluation & Benchmarking Suite for DocumentStructureService in DocLens-AI.

Evaluates DocumentStructureService against 10 distinct document types:
1. Academic Research Paper
2. Technical Documentation
3. Textbook
4. Business Report
5. Legal-Style Document
6. PDF with Numbered Sections
7. PDF without Numbered Sections
8. PDF with Nested Sections
9. PDF with Tables & Figures
10. PDF with Irregular Formatting

Calculates Quantitative Metrics:
- Topic Precision
- Topic Recall
- Hierarchy Accuracy
- Parent-Child Accuracy
- Page Mapping Accuracy
- False Positive Rate

Generates Detailed Diagnostics & Error Analysis:
- Correct Classifications ([OK])
- Incorrect Classifications ([FAIL]) with signal attribution analysis.
"""

import os
import sys
from typing import List, Dict, Any, Tuple
try:
    import pymupdf as fitz
except ImportError:
    import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.document_structure_service import document_structure_service

def generate_pdf_1_academic() -> Tuple[bytes, List[Dict[str, Any]], List[str]]:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "Abstract\nThis paper presents a novel approach to multimodal PDF layout analysis.", fontsize=12)
    p1.insert_text((50, 180), "1. Introduction\nDocument analysis is a critical field in computer vision and natural language processing.", fontsize=14)
    p1.insert_text((50, 300), "Figure 1: Deep neural network architecture diagram for layout extraction", fontsize=10)
    
    p2 = doc.new_page()
    p2.insert_text((50, 80), "2. Methodology\nWe deploy a hybrid transformer architecture combining visual and text features.", fontsize=14)
    p2.insert_text((50, 200), "2.1 Feature Extraction\nVisual feature maps are processed using convolutional backbones.", fontsize=12)
    p2.insert_text((50, 320), "Table 1: Hyperparameter configuration settings", fontsize=10)
    
    p3 = doc.new_page()
    p3.insert_text((50, 80), "3. Experimental Results\nEvaluations conducted across benchmark datasets show significant gains.", fontsize=14)
    p3.insert_text((50, 220), "References\n1. Vaswani et al., Attention is All You Need, NeurIPS 2017.", fontsize=12)

    bytes_data = doc.tobytes()
    doc.close()

    ground_truth = [
        {"title": "Abstract", "level": 1, "page": 1, "parent": None},
        {"title": "1. Introduction", "level": 1, "page": 1, "parent": None},
        {"title": "2. Methodology", "level": 1, "page": 2, "parent": None},
        {"title": "2.1 Feature Extraction", "level": 2, "page": 2, "parent": "2. Methodology"},
        {"title": "3. Experimental Results", "level": 1, "page": 3, "parent": None},
        {"title": "References", "level": 1, "page": 3, "parent": None}
    ]
    noise_lines = [
        "Figure 1: Deep neural network architecture diagram for layout extraction",
        "Table 1: Hyperparameter configuration settings"
    ]
    return bytes_data, ground_truth, noise_lines

def generate_pdf_2_technical() -> Tuple[bytes, List[Dict[str, Any]], List[str]]:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "Overview\nTechnical specifications for API integration.", fontsize=14)
    p1.insert_text((50, 200), "1.0 System Prerequisites\nEnsure Python 3.13 and Uvicorn installed.", fontsize=12)
    p1.insert_text((50, 320), "1.1 Installation Steps\nRun pip install -r requirements.txt.", fontsize=12)

    p2 = doc.new_page()
    p2.insert_text((50, 80), "2.0 API Specification\nDetailed REST API endpoint documentation.", fontsize=14)
    p2.insert_text((50, 200), "2.1 Document Ingestion\nPOST /upload-pdf accepts PDF byte stream.", fontsize=12)
    p2.insert_text((50, 320), "Note: Requires valid authorization header.", fontsize=10)

    bytes_data = doc.tobytes()
    doc.close()

    ground_truth = [
        {"title": "Overview", "level": 1, "page": 1, "parent": None},
        {"title": "1.0 System Prerequisites", "level": 1, "page": 1, "parent": None},
        {"title": "1.1 Installation Steps", "level": 2, "page": 1, "parent": "1.0 System Prerequisites"},
        {"title": "2.0 API Specification", "level": 1, "page": 2, "parent": None},
        {"title": "2.1 Document Ingestion", "level": 2, "page": 2, "parent": "2.0 API Specification"}
    ]
    noise_lines = ["Note: Requires valid authorization header."]
    return bytes_data, ground_truth, noise_lines

def generate_pdf_3_textbook() -> Tuple[bytes, List[Dict[str, Any]], List[str]]:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "Chapter 1 Foundations of Computer Science\nFoundational concepts in algorithms.", fontsize=16)
    p1.insert_text((50, 200), "1.1 Historical Context\nEarly computing mechanisms.", fontsize=13)
    p1.insert_text((50, 300), "1.1.1 Mechanical Calculators\nPascaline and Babbage Analytical Engine.", fontsize=11)

    p2 = doc.new_page()
    p2.insert_text((50, 80), "1.2 Modern Algorithmic Paradigm\nAsymptotic growth and complexity classes.", fontsize=13)
    p2.insert_text((50, 200), "Chapter 2 Advanced Graph Algorithms\nGraph theory and traversal algorithms.", fontsize=16)

    bytes_data = doc.tobytes()
    doc.close()

    ground_truth = [
        {"title": "Chapter 1 Foundations of Computer Science", "level": 1, "page": 1, "parent": None},
        {"title": "1.1 Historical Context", "level": 2, "page": 1, "parent": "Chapter 1 Foundations of Computer Science"},
        {"title": "1.1.1 Mechanical Calculators", "level": 3, "page": 1, "parent": "1.1 Historical Context"},
        {"title": "1.2 Modern Algorithmic Paradigm", "level": 2, "page": 2, "parent": "Chapter 1 Foundations of Computer Science"},
        {"title": "Chapter 2 Advanced Graph Algorithms", "level": 1, "page": 2, "parent": None}
    ]
    return bytes_data, ground_truth, []

def generate_pdf_4_business() -> Tuple[bytes, List[Dict[str, Any]], List[str]]:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "Executive Summary\nAnnual business performance report.", fontsize=14)
    p1.insert_text((50, 200), "Q1 Financial Highlights\nRevenue grew by 24% year-over-year.", fontsize=12)

    p2 = doc.new_page()
    p2.insert_text((50, 80), "Market Analysis\nExpanding TAM across international markets.", fontsize=12)
    p2.insert_text((50, 200), "Risk Factors\nMacroeconomic uncertainties and currency volatility.", fontsize=12)

    bytes_data = doc.tobytes()
    doc.close()

    ground_truth = [
        {"title": "Executive Summary", "level": 1, "page": 1, "parent": None},
        {"title": "Q1 Financial Highlights", "level": 1, "page": 1, "parent": None},
        {"title": "Market Analysis", "level": 1, "page": 2, "parent": None},
        {"title": "Risk Factors", "level": 1, "page": 2, "parent": None}
    ]
    return bytes_data, ground_truth, []

def generate_pdf_5_legal() -> Tuple[bytes, List[Dict[str, Any]], List[str]]:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "Article I Definitions\nFor purposes of this agreement terms are defined herein.", fontsize=13)
    p1.insert_text((50, 200), "Section 1.1 Scope of Service\nProvider shall perform data layout extraction.", fontsize=11)

    p2 = doc.new_page()
    p2.insert_text((50, 80), "Article II Obligations of Parties\nClient shall provide access to target document streams.", fontsize=13)
    p2.insert_text((50, 200), "Clause 2.1.A Termination Terms\nEither party may terminate upon 30 days notice.", fontsize=11)

    bytes_data = doc.tobytes()
    doc.close()

    ground_truth = [
        {"title": "Article I Definitions", "level": 1, "page": 1, "parent": None},
        {"title": "Section 1.1 Scope of Service", "level": 2, "page": 1, "parent": "Article I Definitions"},
        {"title": "Article II Obligations of Parties", "level": 1, "page": 2, "parent": None},
        {"title": "Clause 2.1.A Termination Terms", "level": 3, "page": 2, "parent": "Article II Obligations of Parties"}
    ]
    return bytes_data, ground_truth, []

def generate_pdf_6_numbered() -> Tuple[bytes, List[Dict[str, Any]], List[str]]:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "1. Introduction\nText 1.", fontsize=12)
    p1.insert_text((50, 200), "2. Methodology\nText 2.", fontsize=12)
    p2 = doc.new_page()
    p2.insert_text((50, 80), "3. Evaluation\nText 3.", fontsize=12)

    bytes_data = doc.tobytes()
    doc.close()

    ground_truth = [
        {"title": "1. Introduction", "level": 1, "page": 1, "parent": None},
        {"title": "2. Methodology", "level": 1, "page": 1, "parent": None},
        {"title": "3. Evaluation", "level": 1, "page": 2, "parent": None}
    ]
    return bytes_data, ground_truth, []

def generate_pdf_7_unnumbered() -> Tuple[bytes, List[Dict[str, Any]], List[str]]:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "# Background Overview\nText overview.", fontsize=14)
    p1.insert_text((50, 200), "## Proposed Approach\nText approach.", fontsize=12)
    p2 = doc.new_page()
    p2.insert_text((50, 80), "## Experimental Setup\nText setup.", fontsize=12)

    bytes_data = doc.tobytes()
    doc.close()

    ground_truth = [
        {"title": "Background Overview", "level": 1, "page": 1, "parent": None},
        {"title": "Proposed Approach", "level": 2, "page": 1, "parent": "Background Overview"},
        {"title": "Experimental Setup", "level": 2, "page": 2, "parent": "Background Overview"}
    ]
    return bytes_data, ground_truth, []

def generate_pdf_8_nested() -> Tuple[bytes, List[Dict[str, Any]], List[str]]:
    doc = fitz.open()
    p1 = doc.new_page()
    text = (
        "1. Top Level\nTop text.\n"
        "1.1 Sub Level\nSub text.\n"
        "1.1.1 SubSub Level\nSubSub text.\n"
        "1.1.1.1 DeepSub Level\nDeep text."
    )
    p1.insert_text((50, 80), text, fontsize=12)

    bytes_data = doc.tobytes()
    doc.close()

    ground_truth = [
        {"title": "1. Top Level", "level": 1, "page": 1, "parent": None},
        {"title": "1.1 Sub Level", "level": 2, "page": 1, "parent": "1. Top Level"},
        {"title": "1.1.1 SubSub Level", "level": 3, "page": 1, "parent": "1.1 Sub Level"},
        {"title": "1.1.1.1 DeepSub Level", "level": 4, "page": 1, "parent": "1.1.1 SubSub Level"}
    ]
    return bytes_data, ground_truth, []

def generate_pdf_9_tables_figures() -> Tuple[bytes, List[Dict[str, Any]], List[str]]:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "1. System Overview\nOverview paragraph.", fontsize=14)
    p1.insert_text((50, 200), "Figure 1: High-level system workflow schematic", fontsize=10)
    p1.insert_text((50, 300), "Table 1: Comparative accuracy metrics", fontsize=10)

    p2 = doc.new_page()
    p2.insert_text((50, 80), "2. Empirical Analysis\nAnalysis paragraph.", fontsize=14)
    p2.insert_text((50, 200), "Table 2: Ablation study results", fontsize=10)

    bytes_data = doc.tobytes()
    doc.close()

    ground_truth = [
        {"title": "1. System Overview", "level": 1, "page": 1, "parent": None},
        {"title": "2. Empirical Analysis", "level": 1, "page": 2, "parent": None}
    ]
    noise_lines = [
        "Figure 1: High-level system workflow schematic",
        "Table 1: Comparative accuracy metrics",
        "Table 2: Ablation study results"
    ]
    return bytes_data, ground_truth, noise_lines

def generate_pdf_10_irregular() -> Tuple[bytes, List[Dict[str, Any]], List[str]]:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "Section 1.0 System Architecture\nArchitecture details.", fontsize=12)
    p1.insert_text((50, 200), "1.A Core Engine\nCore engine details.", fontsize=12)

    p2 = doc.new_page()
    p2.insert_text((50, 80), "Appendix A Supplementary Material\nAppendix text.", fontsize=12)
    p2.insert_text((50, 200), "Note: Important implementation details.", fontsize=10)

    bytes_data = doc.tobytes()
    doc.close()

    ground_truth = [
        {"title": "Section 1.0 System Architecture", "level": 1, "page": 1, "parent": None},
        {"title": "1.A Core Engine", "level": 2, "page": 1, "parent": "Section 1.0 System Architecture"},
        {"title": "Appendix A Supplementary Material", "level": 1, "page": 2, "parent": None}
    ]
    noise_lines = ["Note: Important implementation details."]
    return bytes_data, ground_truth, noise_lines

def evaluate_all_documents():
    doc_generators = [
        ("1. Academic Research Paper", generate_pdf_1_academic),
        ("2. Technical Documentation", generate_pdf_2_technical),
        ("3. Textbook", generate_pdf_3_textbook),
        ("4. Business Report", generate_pdf_4_business),
        ("5. Legal-Style Document", generate_pdf_5_legal),
        ("6. Numbered Sections PDF", generate_pdf_6_numbered),
        ("7. Unnumbered Sections PDF", generate_pdf_7_unnumbered),
        ("8. Nested Sections PDF", generate_pdf_8_nested),
        ("9. Tables & Figures PDF", generate_pdf_9_tables_figures),
        ("10. Irregular Formatting PDF", generate_pdf_10_irregular)
    ]

    total_gt_topics = 0
    total_extracted_topics = 0
    total_correct_topics = 0
    total_correct_levels = 0
    total_correct_parents = 0
    total_correct_page_spans = 0
    total_noise_lines = 0
    total_false_positives = 0

    error_log: List[Dict[str, Any]] = []
    correct_log: List[Dict[str, Any]] = []

    print("==========================================================================", flush=True)
    print("      AUTOMATED EVALUATION SUITE FOR DOCUMENT STRUCTURE SERVICE           ", flush=True)
    print("==========================================================================", flush=True)

    for doc_name, generator in doc_generators:
        pdf_bytes, ground_truth, noise_lines = generator()
        manifest = document_structure_service.extract_structure(pdf_bytes, filename=doc_name)
        extracted = manifest.get("flat_nodes", [])

        gt_titles = [g["title"] for g in ground_truth]
        ex_titles = [e["title"] for e in extracted]

        total_gt_topics += len(ground_truth)
        total_extracted_topics += len(extracted)
        total_noise_lines += len(noise_lines)

        matched_gt = set()
        for ex in extracted:
            e_title = ex["title"].strip()
            e_level = ex["level"]
            e_page = ex["page_start"]
            e_parent = ex.get("relationships", {}).get("parent_title")
            e_source = ex.get("source", "unknown")

            # Check if this extracted node matches any noise line
            if any(n.lower() in e_title.lower() for n in noise_lines):
                total_false_positives += 1
                error_log.append({
                    "doc": doc_name,
                    "type": "False Topic Classified from Noise/Caption",
                    "title": e_title,
                    "signal_cause": f"Source: {e_source} | Confidence: {ex.get('confidence', 0.7):.2f}"
                })
                continue

            # Check ground truth match
            matched_gt_node = None
            for gt in ground_truth:
                if gt["title"].lower() in e_title.lower() or e_title.lower() in gt["title"].lower():
                    matched_gt_node = gt
                    break

            if matched_gt_node:
                total_correct_topics += 1
                matched_gt.add(matched_gt_node["title"])

                # Check Level Accuracy
                if matched_gt_node["level"] == e_level:
                    total_correct_levels += 1
                    correct_log.append({
                        "doc": doc_name,
                        "title": e_title,
                        "level": e_level,
                        "signal": e_source
                    })
                else:
                    error_log.append({
                        "doc": doc_name,
                        "type": f"Hierarchy Level Mismatch (Expected L{matched_gt_node['level']}, Got L{e_level})",
                        "title": e_title,
                        "signal_cause": f"Source: {e_source} | Expected L{matched_gt_node['level']}, Got L{e_level}"
                    })

                # Check Parent Accuracy
                gt_parent = matched_gt_node.get("parent")
                if (gt_parent is None and e_parent is None) or (gt_parent and e_parent and gt_parent.lower() in e_parent.lower()):
                    total_correct_parents += 1
                else:
                    error_log.append({
                        "doc": doc_name,
                        "type": "Parent-Child Relationship Mismatch",
                        "title": e_title,
                        "signal_cause": f"Source: {e_source} | Expected Parent: '{gt_parent}', Got: '{e_parent}'"
                    })

                # Check Page Mapping
                if matched_gt_node["page"] == e_page:
                    total_correct_page_spans += 1
            else:
                total_false_positives += 1
                error_log.append({
                    "doc": doc_name,
                    "type": "Unmatched Extra Topic Extracted",
                    "title": e_title,
                    "signal_cause": f"Source: {e_source} | Inferred without explicit ground-truth match"
                })

        # Check for missed ground truth topics (Recall failures)
        for gt in ground_truth:
            if gt["title"] not in matched_gt:
                error_log.append({
                    "doc": doc_name,
                    "type": "Missed Ground Truth Topic (Recall Loss)",
                    "title": gt["title"],
                    "signal_cause": "Failed to trigger markdown, numbering, or typography signal threshold"
                })

    # Compute Metrics
    precision = (total_correct_topics / total_extracted_topics) * 100 if total_extracted_topics > 0 else 0.0
    recall = (total_correct_topics / total_gt_topics) * 100 if total_gt_topics > 0 else 0.0
    hierarchy_accuracy = (total_correct_levels / total_correct_topics) * 100 if total_correct_topics > 0 else 0.0
    parent_child_accuracy = (total_correct_parents / total_correct_topics) * 100 if total_correct_topics > 0 else 0.0
    page_mapping_accuracy = (total_correct_page_spans / total_correct_topics) * 100 if total_correct_topics > 0 else 0.0
    fp_rate = (total_false_positives / total_noise_lines) * 100 if total_noise_lines > 0 else 0.0

    print("\n--------------------------------------------------------------------------", flush=True)
    print("                   QUANTITATIVE PERFORMANCE METRICS                       ", flush=True)
    print("--------------------------------------------------------------------------", flush=True)
    print(f"  * Total Ground-Truth Topics : {total_gt_topics}", flush=True)
    print(f"  * Total Extracted Topics    : {total_extracted_topics}", flush=True)
    print(f"  * Correctly Extracted Topics: {total_correct_topics}", flush=True)
    print(f"  --------------------------------------------------", flush=True)
    print(f"  * TOPIC PRECISION           : {precision:.2f}%", flush=True)
    print(f"  * TOPIC RECALL              : {recall:.2f}%", flush=True)
    print(f"  * HIERARCHY ACCURACY        : {hierarchy_accuracy:.2f}%", flush=True)
    print(f"  * PARENT-CHILD ACCURACY     : {parent_child_accuracy:.2f}%", flush=True)
    print(f"  * PAGE MAPPING ACCURACY     : {page_mapping_accuracy:.2f}%", flush=True)
    print(f"  * FALSE POSITIVE RATE       : {fp_rate:.2f}%", flush=True)
    print("--------------------------------------------------------------------------", flush=True)

    print("\n--------------------------------------------------------------------------", flush=True)
    print("                     VERIFIED CORRECT CLASSIFICATIONS (SAMPLE)           ", flush=True)
    print("--------------------------------------------------------------------------", flush=True)
    for c in correct_log[:10]:
        print(f"  [OK] [{c['doc']}] '{c['title']}' -> Level {c['level']} (Signal: {c['signal']})", flush=True)

    print("\n--------------------------------------------------------------------------", flush=True)
    print("                      ERROR & DIAGNOSTICS REPORT                          ", flush=True)
    print("--------------------------------------------------------------------------", flush=True)
    if not error_log:
        print("  [OK] ZERO FAILURES DETECTED! PERFECT 100% EXTRACTION ACCURACY ACROSS ALL TEST PDF TYPES.", flush=True)
    else:
        for err in error_log:
            print(f"  [FAIL] [{err['doc']}] '{err['title']}' -> {err['type']}", flush=True)
            print(f"         Signal Cause: {err['signal_cause']}", flush=True)

    print("==========================================================================", flush=True)

if __name__ == "__main__":
    evaluate_all_documents()
