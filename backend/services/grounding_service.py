# services/grounding_service.py
"""
Grounding and Hallucination-Protection Layer for DocLens-AI Chatbot.
Verifies LLM draft answers against retrieved PDF evidence before returning final response.
"""

import json
import os
import re
from typing import List, Dict, Any, Optional
from services.llm_service import safe_print, get_groq_client, get_groq_model, execute_groq_completion_with_retry

MAX_VERIFICATION_RETRIES = int(os.getenv("MAX_VERIFICATION_RETRIES", "1"))
INSUFFICIENT_EVIDENCE_RESPONSE = "I couldn't find enough information in the uploaded PDF to answer that reliably."

def check_numeric_grounding(draft_answer: str, context_str: str) -> bool:
    """
    Deterministic helper checking if numbers/percentages in draft_answer exist in context_str.
    """
    if not draft_answer or not context_str:
        return True

    # Find numbers, percentages, currency figures (e.g. $12.0M, 41.18%, 2024, 98.4%)
    answer_numbers = re.findall(r"\b\$?\d+(?:\.\d+)?%?\b", draft_answer)
    context_lower = context_str.lower()

    for num_str in answer_numbers:
        # Ignore common non-data digits like list numbers, page citations [Page 1], or percentage math multiplier (100)
        clean_num = num_str.replace("$", "").replace("%", "").strip()
        if len(clean_num) <= 1 or clean_num in ["100", "100.0", "0"]:  # single digits 1-9 or 100 percentage constant
            continue
        if "deterministic python calculation" in context_lower or "topic manifest" in context_lower:
            continue
        if f"page {clean_num}" in draft_answer.lower() or f"table_{clean_num}" in draft_answer.lower() or f"figure_{clean_num}" in draft_answer.lower() or f"table {clean_num}" in draft_answer.lower() or f"figure {clean_num}" in draft_answer.lower():
            continue

        # Check presence in context string (exact or token substring)
        if clean_num not in context_lower and not any(clean_num in token for token in context_lower.replace("/", " ").replace("-", " ").split()):
            safe_print(f"[Grounding Warning] Number '{num_str}' in draft answer not found in context evidence!")
            return False

    return True

def verify_grounding(
    draft_answer: str, 
    context_chunks: List[str], 
    question: str,
    history: Optional[List[dict]] = None
) -> dict:
    """
    Evaluates whether the draft answer is fully grounded in the retrieved PDF context
    and ongoing conversation history. Returns structured JSON with verdict and feedback.
    """
    if not draft_answer or not draft_answer.strip():
        return {
            "supported_by_evidence": False,
            "factual_claims_supported": False,
            "numbers_supported": False,
            "dates_supported": False,
            "citations_supported": False,
            "contains_invented_info": True,
            "verdict": "INSUFFICIENT_EVIDENCE",
            "feedback": "Empty response generated."
        }

    # If LLM itself stated it could not find information
    insufficient_signals = [
        "does not contain", "do not contain", "not contain", "couldn't find enough information",
        "could not find enough information", "not found in the", "no information about",
        "cannot supply", "cannot provide", "no mention of", "not mentioned in", "not provided in",
        "not available in the"
    ]
    if any(sig in draft_answer.lower() for sig in insufficient_signals):
        return {
            "supported_by_evidence": True,
            "factual_claims_supported": True,
            "numbers_supported": True,
            "dates_supported": True,
            "citations_supported": True,
            "contains_invented_info": False,
            "verdict": "INSUFFICIENT_EVIDENCE",
            "feedback": "Explicit insufficient information response."
        }

    combined_context = "\n\n".join(context_chunks)

    # 1. Deterministic Numerical Check
    numeric_pass = check_numeric_grounding(draft_answer, combined_context)

    # 2. Groq LLM Verifier Call
    try:
        client = get_groq_client()
        model_name = get_groq_model()

        verifier_system_prompt = (
            "You are a strict grounding and hallucination verification auditor for a PDF document RAG system. "
            "Your job is to audit a draft answer against the provided PDF evidence context chunks, conversation history, and user question.\n\n"
            "MUST CHECK:\n"
            "1. Is the draft answer supported by the retrieved PDF context and ongoing conversation history?\n"
            "2. Are all factual claims about the document supported by context or preceding conversation?\n"
            "3. Are numbers, metrics, and percentages strictly supported?\n"
            "4. Are dates and years supported?\n"
            "5. Are page/table/figure citations valid?\n"
            "6. Did the draft answer invent outside information not in the document or conversation?\n\n"
            "CONVERSATIONAL RULES:\n"
            "- If the user asks a follow-up, clarification, summary, comparison, or question referencing previous conversation turns, verify that the answer is consistent with the conversation history and document context.\n"
            "- Return 'PASS' if the answer is grounded in evidence or consistent with the conversation history.\n"
            "- Return 'INSUFFICIENT_EVIDENCE' only if neither the context nor conversation contains enough information to answer reliably.\n"
            "- Return 'FAIL' if the draft contains ungrounded claims, invented numbers, or false assumptions.\n\n"
            "You MUST respond ONLY with a raw JSON object matching this structure exactly:\n"
            "{\n"
            '  "supported_by_evidence": true,\n'
            '  "factual_claims_supported": true,\n'
            '  "numbers_supported": true,\n'
            '  "dates_supported": true,\n'
            '  "citations_supported": true,\n'
            '  "contains_invented_info": false,\n'
            '  "verdict": "PASS",\n'
            '  "feedback": "Reason or feedback if verification failed, else empty string"\n'
            "}"
        )

        history_snippet = ""
        if history:
            valid_h = [m for m in history if isinstance(m, dict) and m.get("content")]
            if valid_h:
                h_lines = [f"{m.get('role', 'user').capitalize()}: {m.get('content').strip()}" for m in valid_h[-8:]]
                history_snippet = f"\n\n<CONVERSATION_HISTORY>\n" + "\n".join(h_lines) + "\n</CONVERSATION_HISTORY>"

        verifier_user_prompt = f"""<PDF_CONTEXT_EVIDENCE>
{combined_context[:8000]}
</PDF_CONTEXT_EVIDENCE>{history_snippet}

<USER_QUESTION>
{question}
</USER_QUESTION>

<DRAFT_ANSWER_TO_AUDIT>
{draft_answer}
</DRAFT_ANSWER_TO_AUDIT>"""

        response = execute_groq_completion_with_retry(
            client,
            model=model_name,
            max_tokens=300,
            temperature=0.0,
            messages=[
                {"role": "system", "content": verifier_system_prompt},
                {"role": "user", "content": verifier_user_prompt}
            ]
        )

        raw_json = (response.choices[0].message.content or "").strip()
        if "<think>" in raw_json:
            raw_json = re.sub(r"<think>.*?</think>", "", raw_json, flags=re.DOTALL).strip()

        # Clean JSON markdown fences if present
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:]
        if raw_json.startswith("```"):
            raw_json = raw_json[3:]
        if raw_json.endswith("```"):
            raw_json = raw_json[:-3]

        verification_result = json.loads(raw_json.strip())

        # Override numbers_supported if deterministic check failed
        if not numeric_pass:
            verification_result["numbers_supported"] = False
            verification_result["verdict"] = "FAIL"
            verification_result["feedback"] += " Deterministic check detected ungrounded numbers in draft answer."

        return verification_result

    except Exception as e:
        safe_print(f"[Grounding Verifier Warning]: Verifier call failed ({str(e)}). Defaulting based on numeric check.")
        if not numeric_pass:
            return {
                "supported_by_evidence": False,
                "factual_claims_supported": True,
                "numbers_supported": False,
                "dates_supported": True,
                "citations_supported": True,
                "contains_invented_info": True,
                "verdict": "FAIL",
                "feedback": "Deterministic numerical grounding check failed."
            }
        return {
            "supported_by_evidence": True,
            "factual_claims_supported": True,
            "numbers_supported": True,
            "dates_supported": True,
            "citations_supported": True,
            "contains_invented_info": False,
            "verdict": "PASS",
            "feedback": ""
        }

def generate_grounded_response(
    context_chunks: List[str], 
    question: str, 
    history: Optional[List[Dict[str, str]]] = None,
    generate_fn = None
) -> str:
    """
    Pipeline:
    Retrieved evidence -> LLM -> Draft answer -> Grounding verification -> Final answer
    
    Caps retries at MAX_VERIFICATION_RETRIES (1 retry).
    Returns INSUFFICIENT_EVIDENCE_RESPONSE if ungrounded or evidence is missing.
    """
    if not context_chunks:
        if history and any(m.get("content") for m in history if isinstance(m, dict)):
            if generate_fn:
                return generate_fn(context_chunks=["[Conversation Mode: Using discussion history]"], question=question, history=history, feedback="")
            return default_llm_generate(context_chunks=["[Conversation Mode: Using discussion history]"], question=question, history=history, feedback="")
        return INSUFFICIENT_EVIDENCE_RESPONSE

    # If context itself indicates insufficient evidence
    combined_ctx = "\n\n".join(context_chunks)
    if "completely unmentioned" in combined_ctx.lower() and len(combined_ctx) < 200:
        return INSUFFICIENT_EVIDENCE_RESPONSE

    current_feedback = ""
    attempt = 0

    while attempt <= MAX_VERIFICATION_RETRIES:
        attempt += 1

        if generate_fn:
            draft_answer = generate_fn(context_chunks=context_chunks, question=question, history=history, feedback=current_feedback)
        else:
            draft_answer = default_llm_generate(context_chunks=context_chunks, question=question, history=history, feedback=current_feedback)

        safe_print(f"\n[Grounding Audit] Verification Attempt {attempt}/{MAX_VERIFICATION_RETRIES + 1}...")
        audit = verify_grounding(draft_answer, context_chunks, question, history=history)
        verdict = audit.get("verdict", "PASS")
        feedback = audit.get("feedback", "")

        safe_print(f"[Grounding Audit Result]: Verdict='{verdict}' | Feedback='{feedback}'")

        if verdict == "PASS":
            return draft_answer

        if verdict == "INSUFFICIENT_EVIDENCE":
            return INSUFFICIENT_EVIDENCE_RESPONSE

        # Verdict is FAIL: Set feedback for retry if under retry limit
        if attempt <= MAX_VERIFICATION_RETRIES:
            safe_print(f"[Grounding Layer] Draft failed verification: {feedback}. Triggering retry {attempt}/{MAX_VERIFICATION_RETRIES}...")
            current_feedback = feedback
        else:
            safe_print(f"[Grounding Layer] Max retries ({MAX_VERIFICATION_RETRIES}) reached. Fallback to insufficient evidence response.")
            return INSUFFICIENT_EVIDENCE_RESPONSE

    return INSUFFICIENT_EVIDENCE_RESPONSE

def default_llm_generate(context_chunks: List[str], question: str, history: Optional[List[dict]] = None, feedback: str = "") -> str:
    """
    Internal wrapper calling Groq LLM to produce initial or revised draft answer.
    """
    from services.token_service import count_tokens
    from services.rate_limiter_service import groq_rate_limiter

    client = get_groq_client()
    model_name = get_groq_model()

    system_instruction = (
        "You are an expert, highly accurate, and conversational AI document assistant for DocLens-AI.\n"
        "- Maintain complete conversational continuity with the user across dialogue turns. You have full access to the ongoing conversation history.\n"
        "- For questions about the PDF document, ground your answers strictly in the provided document <context> chunks.\n"
        "- For conversational follow-ups, questions referring to previous messages (e.g., 'what did I ask before', 'summarize our chat', 'elaborate on your second point', 'compare what you just said'), seamlessly reference the conversation history and previous assistant answers.\n"
        "- Do not make up facts outside the document or conversation.\n"
        "- If structured table data or deterministic calculation results are provided in the context, incorporate them directly and explain the results clearly.\n"
        "- Provide step-by-step logic, clear explanations, formatted code blocks, and exact page or table citations (e.g. [Page 1], [Page 2, Table table_1]) when citing document facts.\n"
        "- Only if a document-specific detail is completely missing from both the context chunks and the conversation history, politely inform the user."
    )

    if feedback:
        system_instruction += f"\n\nCRITICAL AUDIT FEEDBACK FROM PREVIOUS DRAFT: The previous draft was rejected for ungrounded claims/numbers: {feedback}. Remove any unsupported claims or numbers immediately and rely strictly on the context chunks and conversation history."

    combined_context = "\n\n--- Chunk ---\n\n".join(context_chunks)
    if len(combined_context) > 12000:
        combined_context = combined_context[:12000] + "\n\n[...context truncated for size...]"

    capped_history = []
    if history:
        valid = [m for m in history if isinstance(m, dict) and m.get("content")]
        capped_history = valid[-14:]

    messages = [{"role": "system", "content": system_instruction}]

    for msg in capped_history:
        role = "user" if msg.get("role") in ("user", "human") else "assistant"
        messages.append({"role": role, "content": msg.get("content").strip()})

    prompt = f"""Document Evidence Context:
<context>
{combined_context}
</context>

User Question:
{question}

Please answer the user's question accurately based on the document <context> and our ongoing conversation history:"""

    messages.append({"role": "user", "content": prompt})

    est_tokens = count_tokens(system_instruction) + count_tokens(prompt) + 1024
    groq_rate_limiter.wait_for_capacity(est_tokens)

    response = execute_groq_completion_with_retry(
        client,
        model=model_name,
        max_tokens=1024,
        temperature=0.0,
        messages=messages
    )

    ans = response.choices[0].message.content or ""
    if "<think>" in ans:
        ans = re.sub(r"<think>.*?</think>", "", ans, flags=re.DOTALL).strip()
    return ans
