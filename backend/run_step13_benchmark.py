# run_step13_benchmark.py
"""
Step 13: End-to-End Accuracy Benchmark Execution Engine for DocLens-AI RAG Pipeline.

Evaluates 5 Retrieval Configurations:
A. Vector-only
B. BM25-only
C. Hybrid
D. Hybrid + Reranker
E. Final Pipeline (Rewriter + Table/Figure + Context Expansion + Grounding + Citation)

Measures:
- Recall@1, Recall@3, Recall@5, Recall@10
- MRR, nDCG@5, nDCG@10
- Answer Correctness, Groundedness, Citation Accuracy, Page-Number Accuracy, Numerical Accuracy, Hallucination Rate, Not-Found Detection.
"""

import json
import math
import os
import re
import sys
import time
from typing import List, Dict, Any

from services.vector_service import search_knowledge_base, add_to_knowledge_base, clear_knowledge_base
from services.bm25_service import bm25_service
from services.context_expansion_service import context_expansion_service
from services.hybrid_retriever_service import retrieve_hybrid_chunks
from services.reranker_service import reranker_service
from services.retriever_service import retrieve_relevant_chunks_with_metadata
from services.table_service import table_service
from services.figure_service import figure_service
from services.topic_service import topic_service
from services.query_rewriter_service import rewrite_query
from services.grounding_service import generate_grounded_response, INSUFFICIENT_EVIDENCE_RESPONSE
from services.citation_service import extract_sources_from_metadata, attach_sources_to_answer

BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), "benchmark_dataset_50.json")

# =============================================================================
# 1. SEED EXPANDED BENCHMARK KNOWLEDGE BASE (50-Question Coverage)
# =============================================================================
def seed_step13_knowledge_base():
    clear_knowledge_base()
    bm25_service.clear_index()
    context_expansion_service.clear_chunks()
    table_service.clear_tables()
    figure_service.clear_figures()
    topic_service.clear_topics()

    chunks = [
        {
            "chunk_id": "doc_step13_p1_c1",
            "document_id": "doc_step13",
            "document_name": "step13_benchmark.pdf",
            "page_number": 1,
            "page_start": 1,
            "page_end": 1,
            "section": "Introduction",
            "heading": "AI Performance",
            "content_type": "text",
            "table_id": "",
            "figure_id": "",
            "text": "Artificial intelligence and machine learning are revolutionizing automated PDF processing. Model performance achieved 98.4% accuracy across 15,000 benchmark documents evaluated in Q3 2026. Key limitations include rate limits on public API endpoints and memory constraints."
        },
        {
            "chunk_id": "doc_step13_p2_c2",
            "document_id": "doc_step13",
            "document_name": "step13_benchmark.pdf",
            "page_number": 2,
            "page_start": 2,
            "page_end": 2,
            "section": "Methodology",
            "heading": "RAG Architecture",
            "content_type": "text",
            "table_id": "",
            "figure_id": "",
            "text": "Methodology involved multi-stage RAG retrieval paired with hierarchical summarization pipelines to split large documents cleanly. The embedding dimension is 384 using sentence-transformers/all-MiniLM-L6-v2. Vector similarity search and BM25 lexical search candidates are fused using Reciprocal Rank Fusion (RRF) formula 1/(k + rank). Reranking uses cross-encoder/ms-marco-MiniLM-L-6-v2. Parent-child chunk expansion matches child chunks first and expands to full parent section blocks."
        },
        {
            "chunk_id": "doc_step13_p3_c3",
            "document_id": "doc_step13",
            "document_name": "step13_benchmark.pdf",
            "page_number": 3,
            "page_start": 3,
            "page_end": 3,
            "section": "Financial Results",
            "heading": "Table 1",
            "content_type": "table",
            "table_id": "table_1",
            "figure_id": "",
            "caption": "Company Financial Performance",
            "text": "Table 1: Company Financial Performance (Section Financial Results)\n| Metric | 2023 | 2024 |\n|---|---|---|\n| Revenue | $8.5M | $12.0M |\n| Net Profit | $1.5M | $2.5M |\n| Expenses | $7.0M | $9.5M |"
        },
        {
            "chunk_id": "doc_step13_p4_c4",
            "document_id": "doc_step13",
            "document_name": "step13_benchmark.pdf",
            "page_number": 4,
            "page_start": 4,
            "page_end": 4,
            "section": "Model Architecture",
            "heading": "Figure 4",
            "content_type": "figure",
            "table_id": "",
            "figure_id": "figure_4",
            "caption": "Figure 4: Transformer Architecture System Flowchart",
            "text": "Figure 4: Transformer Architecture System Flowchart (PNG Format). Inputs pass through positional encoding into multi-head attention modules. Encoder outputs feed into Decoder attention layers. The architecture flowchart image is located on Page 4."
        },
        {
            "chunk_id": "doc_step13_p5_c5",
            "document_id": "doc_step13",
            "document_name": "step13_benchmark.pdf",
            "page_number": 5,
            "page_start": 5,
            "page_end": 5,
            "section": "Summarization System",
            "heading": "Token Limits",
            "content_type": "text",
            "table_id": "",
            "figure_id": "",
            "text": "For summarization, the max token limit is 6,500 tokens per chunk with 400 overlap tokens. Map-reduce chunking synthesizes section summaries into a final summary."
        },
        {
            "chunk_id": "doc_step13_p6_c6",
            "document_id": "doc_step13",
            "document_name": "step13_benchmark.pdf",
            "page_number": 6,
            "page_start": 6,
            "page_end": 6,
            "section": "Rate Limiting",
            "heading": "Groq Retry Logic",
            "content_type": "text",
            "table_id": "",
            "figure_id": "",
            "text": "HTTP 429 rate limit handling details are on Page 6. HTTP 429 errors from Groq API are handled using server-provided retry-after wait durations and exponential backoff retry logic up to 3 retries."
        },
        {
            "chunk_id": "doc_step13_p7_c7",
            "document_id": "doc_step13",
            "document_name": "step13_benchmark.pdf",
            "page_number": 7,
            "page_start": 7,
            "page_end": 7,
            "section": "Grounding Layer",
            "heading": "Hallucination Protection",
            "content_type": "text",
            "table_id": "",
            "figure_id": "",
            "text": "The Grounding Verifier Layer audits LLM draft answers against PDF context chunks to enforce strict evidence support and block hallucinations."
        },
        {
            "chunk_id": "doc_step13_p8_c8",
            "document_id": "doc_step13",
            "document_name": "step13_benchmark.pdf",
            "page_number": 8,
            "page_start": 8,
            "page_end": 8,
            "section": "Document Navigator",
            "heading": "AI Navigator",
            "content_type": "text",
            "table_id": "",
            "figure_id": "",
            "text": "The AI Document Navigator extracts definitions, formulas, figures, tables, and section structures into an interactive PDF outline."
        },
        {
            "chunk_id": "doc_step13_p32_c32",
            "document_id": "doc_step13",
            "document_name": "step13_benchmark.pdf",
            "page_number": 32,
            "page_start": 32,
            "page_end": 32,
            "section": "Enterprise Deployment",
            "heading": "SLA & Scale",
            "content_type": "text",
            "table_id": "",
            "figure_id": "",
            "text": "Enterprise deployment on page 32 demonstrated 99.9% uptime SLA across distributed clusters for high-volume enterprise document processing evaluated in 2026."
        }
    ]

    add_to_knowledge_base(chunks)
    bm25_service.add_documents(chunks)
    context_expansion_service.set_document_chunks(chunks)
    table_service.extract_and_register_from_chunks(chunks)
    figure_service.extract_and_register_from_chunks(chunks)
    topic_service.extract_and_register_from_chunks(chunks, filename="step13_benchmark.pdf")
    return chunks


# =============================================================================
# 2. RETRIEVAL CONFIGURATIONS (Configs A, B, C, D, E)
# =============================================================================

def config_a_vector_only(query: str, max_k: int = 10) -> List[int]:
    """Config A: Vector-only retrieval via ChromaDB."""
    vec_res = search_knowledge_base(query, top_k=max_k)
    pages = []
    for d in vec_res:
        pg = d.get("metadata", {}).get("page_number", d.get("metadata", {}).get("page", 1))
        pages.append(int(pg))
    return pages

def config_b_bm25_only(query: str, max_k: int = 10) -> List[int]:
    """Config B: BM25-only lexical retrieval."""
    bm25_res = bm25_service.search(query, top_k=max_k)
    pages = []
    for d in bm25_res:
        pg = d.get("page_number", d.get("page", 1))
        pages.append(int(pg))
    return pages

def config_c_hybrid(query: str, max_k: int = 10) -> List[int]:
    """Config C: Hybrid retrieval (Vector + BM25 RRF)."""
    hybrid_res = retrieve_hybrid_chunks(query, hybrid_top_k=max_k)
    pages = []
    for d in hybrid_res:
        pg = d.get("page_number", d.get("page", 1))
        pages.append(int(pg))
    return pages

def config_d_hybrid_reranker(query: str, max_k: int = 10) -> List[int]:
    """Config D: Hybrid + Reranker."""
    hybrid_res = retrieve_hybrid_chunks(query, hybrid_top_k=15)
    reranked = reranker_service.rerank(query, hybrid_res, top_k=max_k)
    pages = []
    for d in reranked:
        pg = d.get("page_number", d.get("page", 1))
        pages.append(int(pg))
    return pages

def config_e_final_pipeline(item: Dict[str, Any], max_k: int = 10) -> Dict[str, Any]:
    """
    Config E: Final Pipeline (Rewriter + Table/Figure + Context Expansion + Grounding + Citation).
    """
    q = item["question"]
    history = item.get("history")

    retrieval_query = rewrite_query(q, history)
    topic_intent = topic_service.classify_topic_intent(retrieval_query)
    table_intent = table_service.classify_query_intent(retrieval_query)
    visual_intent = figure_service.classify_visual_query(retrieval_query)

    context_chunks = []
    raw_meta = []

    if topic_intent["is_topic_query"] and (topic_service.get_topics() or context_expansion_service.doc_chunks):
        topic_block, topic_meta = topic_service.retrieve_topic_context(retrieval_query, topic_intent)
        context_chunks.append(topic_block)
        raw_meta.extend(topic_meta)
        if topic_intent.get("query_type") == "detail":
            hybrid_text, text_meta = retrieve_relevant_chunks_with_metadata(retrieval_query, top_k=2)
            context_chunks.extend(hybrid_text)
            raw_meta.extend(text_meta)

    elif table_intent["is_table_query"] and table_service.get_tables():
        tbl = table_service.table_aware_retrieval(retrieval_query)
        if tbl:
            calc = table_service.calculate_table_metrics(tbl, table_intent["calc_type"], retrieval_query)
            context_chunks.append(table_service.format_table_context(tbl, calc))
            raw_meta.append({"type": "table", "table_id": tbl["table_id"], "page_number": tbl["page_number"]})
            
            hybrid_text, text_meta = retrieve_relevant_chunks_with_metadata(retrieval_query, top_k=2)
            context_chunks.extend(hybrid_text)
            raw_meta.extend(text_meta)

    elif visual_intent["is_visual_query"] and figure_service.get_figures():
        fig = figure_service.identify_relevant_figure(retrieval_query, target_num=visual_intent["target_num"])
        if fig:
            evidence = None
            if visual_intent["requires_vision_ai"] and fig.get("image_id"):
                evidence = figure_service.analyze_visual_evidence(fig, retrieval_query)
            context_chunks.append(figure_service.format_figure_context(fig, evidence))
            raw_meta.append({"type": "figure", "figure_id": fig["figure_id"], "page_number": fig["page_number"]})
            
            hybrid_text, text_meta = retrieve_relevant_chunks_with_metadata(retrieval_query, top_k=2)
            context_chunks.extend(hybrid_text)
            raw_meta.extend(text_meta)

    if not context_chunks:
        text_chunks, text_meta = retrieve_relevant_chunks_with_metadata(retrieval_query, top_k=max_k)
        context_chunks.extend(text_chunks)
        raw_meta.extend(text_meta)

    retrieved_pages = [int(m.get("page_number", m.get("page_start", 1))) for m in raw_meta]

    if not context_chunks:
        answer = INSUFFICIENT_EVIDENCE_RESPONSE
        sources = []
    else:
        raw_ans = generate_grounded_response(context_chunks, q, history)
        sources = extract_sources_from_metadata(raw_meta or context_chunks)
        answer = attach_sources_to_answer(raw_ans, sources, append_markdown=True)

    return {
        "retrieved_pages": list(dict.fromkeys(retrieved_pages)),
        "retrieved_chunks": context_chunks,
        "answer": answer,
        "sources": sources
    }


# =============================================================================
# 3. METRIC COMPUTATION (Recall@1/3/5/10, MRR, nDCG@5/10, Accuracy, Grounding)
# =============================================================================

def compute_recall_at_k(targets: List[int], retrieved: List[int], k: int) -> float:
    if not targets:
        return 1.0
    top_k = retrieved[:k]
    hits = [p for p in targets if p in top_k]
    return len(hits) / len(targets)

def compute_mrr(targets: List[int], retrieved: List[int]) -> float:
    if not targets:
        return 1.0
    for rank, p in enumerate(retrieved, start=1):
        if p in targets:
            return 1.0 / rank
    return 0.0

def compute_ndcg_at_k(targets: List[int], retrieved: List[int], k: int) -> float:
    if not targets:
        return 1.0
    top_k = retrieved[:k]
    dcg = 0.0
    for idx, p in enumerate(top_k, start=1):
        rel = 1.0 if p in targets else 0.0
        dcg += rel / math.log2(idx + 1)
    
    # Ideal DCG
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(targets), k) + 1))
    return dcg / idcg if idcg > 0 else 0.0

def evaluate_step13_answer(item: Dict[str, Any], answer: str, retrieved_pages: List[int], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    target_ans = item["expected_answer"]
    target_pages = item["expected_pages"]
    keywords = item.get("target_keywords", [])
    cat = item["category"]

    is_non_existent = not target_pages or "NOT exist" in cat

    if is_non_existent:
        is_safe_fallback = INSUFFICIENT_EVIDENCE_RESPONSE.lower() in answer.lower() or "couldn't find" in answer.lower()
        return {
            "correct": is_safe_fallback,
            "grounded": is_safe_fallback,
            "citation_acc": 1.0,
            "page_acc": 1.0,
            "num_acc": 1.0,
            "hallucination": 0.0 if is_safe_fallback else 1.0,
            "not_found_correct": 1.0 if is_safe_fallback else 0.0
        }

    # Keyword hits
    kw_hits = sum(1 for kw in keywords if kw.lower() in answer.lower())
    is_correct = (kw_hits / len(keywords)) >= 0.5 if keywords else len(answer.strip()) > 10

    # Numerical Accuracy check
    num_match = True
    nums_in_target = re.findall(r"\b\$?\d+(?:\.\d+)?%?\b", target_ans)
    if nums_in_target:
        num_hits = sum(1 for n in nums_in_target if n.lower() in answer.lower())
        num_match = (num_hits == len(nums_in_target))

    # Page accuracy check
    page_match = any(p in retrieved_pages for p in target_pages)
    
    # Citation accuracy check
    cite_match = any(f"Page {p}" in answer or any(s.get("page_number") == p for s in sources) for p in target_pages)

    # Hallucination check
    hallucination = 0.0 if (is_correct and num_match) else 1.0

    return {
        "correct": is_correct and num_match,
        "grounded": is_correct,
        "citation_acc": 1.0 if cite_match else 0.0,
        "page_acc": 1.0 if page_match else 0.0,
        "num_acc": 1.0 if num_match else 0.0,
        "hallucination": hallucination,
        "not_found_correct": 1.0
    }


# =============================================================================
# 4. STEP 13 BENCHMARK RUNNER & REPORT GENERATOR
# =============================================================================

def run_step13_evaluation():
    print("========== DOCLENS-AI STEP 13: END-TO-END ACCURACY BENCHMARK ==========\n")
    
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"Loaded benchmark dataset containing {len(dataset)} questions across 14 categories.\n")
    seed_step13_knowledge_base()

    configs = [
        ("A. Vector-only", lambda q, item: config_a_vector_only(q, max_k=10)),
        ("B. BM25-only", lambda q, item: config_b_bm25_only(q, max_k=10)),
        ("C. Hybrid", lambda q, item: config_c_hybrid(q, max_k=10)),
        ("D. Hybrid + Reranker", lambda q, item: config_d_hybrid_reranker(q, max_k=10)),
        ("E. Final Pipeline", lambda q, item: config_e_final_pipeline(item, max_k=10))
    ]

    report_table = []
    final_category_stats = {}
    failure_cases = []

    for cfg_name, cfg_fn in configs:
        print(f"--- Running Evaluation for Configuration: {cfg_name} ---")
        
        r1_list, r3_list, r5_list, r10_list = [], [], [], []
        mrr_list, ndcg5_list, ndcg10_list = [], [], []
        correct_list, ground_list, cite_list, page_list, num_list, hall_list, notfound_list = [], [], [], [], [], [], []

        for item in dataset:
            q = item["question"]
            targets = item["expected_pages"]

            if cfg_name == "E. Final Pipeline":
                out_e = cfg_fn(q, item)
                ret_pages = out_e["retrieved_pages"]
                ans_eval = evaluate_step13_answer(item, out_e["answer"], ret_pages, out_e["sources"])
                
                cat = item["category"]
                if cat not in final_category_stats:
                    final_category_stats[cat] = {"total": 0, "passed": 0}
                final_category_stats[cat]["total"] += 1
                if ans_eval["correct"]:
                    final_category_stats[cat]["passed"] += 1
                else:
                    failure_cases.append({
                        "id": item["id"],
                        "category": cat,
                        "question": q,
                        "expected": item["expected_answer"],
                        "actual": out_e["answer"],
                        "reason": "Numerical/grounding mismatch or missing context"
                    })
            else:
                ret_pages = cfg_fn(q, item)
                # Mock answer for ret-only configs
                dummy_ans = f"Retrieved pages: {ret_pages}"
                ans_eval = evaluate_step13_answer(item, dummy_ans, ret_pages, [])

            r1_list.append(compute_recall_at_k(targets, ret_pages, 1))
            r3_list.append(compute_recall_at_k(targets, ret_pages, 3))
            r5_list.append(compute_recall_at_k(targets, ret_pages, 5))
            r10_list.append(compute_recall_at_k(targets, ret_pages, 10))
            mrr_list.append(compute_mrr(targets, ret_pages))
            ndcg5_list.append(compute_ndcg_at_k(targets, ret_pages, 5))
            ndcg10_list.append(compute_ndcg_at_k(targets, ret_pages, 10))

            correct_list.append(ans_eval["correct"])
            ground_list.append(ans_eval["grounded"])
            cite_list.append(ans_eval["citation_acc"])
            page_list.append(ans_eval["page_acc"])
            num_list.append(ans_eval["num_acc"])
            hall_list.append(ans_eval["hallucination"])
            notfound_list.append(ans_eval["not_found_correct"])

        report_table.append({
            "config": cfg_name,
            "r1": f"{sum(r1_list)/len(r1_list)*100:.1f}%",
            "r3": f"{sum(r3_list)/len(r3_list)*100:.1f}%",
            "r5": f"{sum(r5_list)/len(r5_list)*100:.1f}%",
            "r10": f"{sum(r10_list)/len(r10_list)*100:.1f}%",
            "mrr": f"{sum(mrr_list)/len(mrr_list):.3f}",
            "ndcg5": f"{sum(ndcg5_list)/len(ndcg5_list):.3f}",
            "ndcg10": f"{sum(ndcg10_list)/len(ndcg10_list):.3f}",
            "accuracy": f"{sum(correct_list)/len(correct_list)*100:.1f}%",
            "citation": f"{sum(cite_list)/len(cite_list)*100:.1f}%",
            "hallucination": f"{sum(hall_list)/len(hall_list)*100:.1f}%"
        })

    # =========================================================================
    # 5. OUTPUT STEP 13 EVALUATION REPORT
    # =========================================================================
    total_q = len(dataset)
    passed_q = sum(1 for c in final_category_stats.values() for _ in range(c["passed"]))
    # Re-calc exact passed questions on Config E
    pipeline_accuracy = report_table[-1]["accuracy"]
    passed_cnt = int(total_q * (sum([c["passed"] for c in final_category_stats.values()]) / total_q))

    print("\n\n=======================================================================")
    print("                STEP 13: EVALUATION BENCHMARK REPORT RESULTS            ")
    print("=======================================================================\n")
    print(f"Total Benchmark Questions: {total_q}")
    print(f"Final Pipeline Accuracy:   {pipeline_accuracy}")
    print(f"Citation Accuracy:         {report_table[-1]['citation']}")
    print(f"Hallucination Rate:        {report_table[-1]['hallucination']}\n")

    print("### RETRIEVAL & ANSWER CONFIGURATION COMPARISON TABLE\n")
    print("| Configuration | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | nDCG@5 | nDCG@10 | Answer Accuracy | Citation Acc | Hallucination |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in report_table:
        print(f"| {r['config']} | {r['r1']} | {r['r3']} | {r['r5']} | {r['r10']} | {r['mrr']} | {r['ndcg5']} | {r['ndcg10']} | {r['accuracy']} | {r['citation']} | {r['hallucination']} |")

    print("\n### CATEGORY-WISE ACCURACY BREAKDOWN\n")
    print("| Category | Total Questions | Passed | Accuracy |")
    print("| :--- | :--- | :--- | :--- |")
    for cat, stat in sorted(final_category_stats.items()):
        acc = (stat["passed"] / stat["total"]) * 100 if stat["total"] > 0 else 0.0
        print(f"| {cat} | {stat['total']} | {stat['passed']} | {acc:.1f}% |")

    print("\n=======================================================================")
    print("                   FAILURE EXAMPLES & ROOT CAUSE ANALYSIS              ")
    print("=======================================================================")
    if failure_cases:
        for idx, fail in enumerate(failure_cases[:5], start=1):
            print(f"\nFailure {idx}: [{fail['category']}] (Q ID: {fail['id']})")
            print(f"  Question: {fail['question']}")
            print(f"  Expected: {fail['expected']}")
            print(f"  Actual:   {fail['actual'][:150]}...")
            print(f"  Cause:    {fail['reason']}")
    else:
        print("\nZero critical failures detected in final pipeline benchmark!")

if __name__ == "__main__":
    run_step13_evaluation()
