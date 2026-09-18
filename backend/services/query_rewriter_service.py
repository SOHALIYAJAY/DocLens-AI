# services/query_rewriter_service.py
"""
Query Rewriter Service for Conversational PDF Assistant.
Converts conversational follow-ups and pronoun-based questions into standalone retrieval queries.
"""

import re
from typing import List, Dict, Optional
from services.llm_service import safe_print, get_groq_client, get_groq_model, execute_groq_completion_with_retry

def log_query_rewriting(original_question: str, retrieval_query: str):
    """
    Logs the original question and the resulting retrieval query using the required format:
    
    [QUERY]
    Original: ...

    [QUERY]
    Retrieval query: ...
    """
    safe_print("\n[QUERY]")
    safe_print(f"Original: {original_question}")
    safe_print("\n[QUERY]")
    safe_print(f"Retrieval query: {retrieval_query}\n")

def rewrite_query(question: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """
    Analyzes user question and recent conversation history to produce a standalone retrieval query.
    
    - Limits conversation history window (max recent 4 messages / 2 turns).
    - Preserves standalone questions and unrelated new questions.
    - Rewrites follow-up questions and pronoun references into clear self-contained queries.
    - Prints mandatory [QUERY] log structure.
    
    Args:
        question (str): Latest user question.
        history (Optional[List[Dict[str, str]]]): Conversation history list.
        
    Returns:
        str: Standalone query for retrieval.
    """
    if not question or not question.strip():
        log_query_rewriting(question or "", question or "")
        return question or ""
    clean_question = question.strip()

    # Quick check for greetings / conversational pleasantries / direct commands
    q_norm = clean_question.lower().strip("?!., ")
    if q_norm in [
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "who are you", "what can you do", "help", "thanks", "thank you",
        "bye", "goodbye"
    ]:
        log_query_rewriting(clean_question, clean_question)
        return clean_question

    # If no history is provided or history is empty, query is already standalone
    if not history:
        log_query_rewriting(clean_question, clean_question)
        return clean_question

    # Filter non-empty valid message objects
    valid_history = [
        msg for msg in history 
        if isinstance(msg, dict) and msg.get("content") and msg.get("content").strip()
    ]

    if not valid_history:
        log_query_rewriting(clean_question, clean_question)
        return clean_question

    # Cap history window to recent 10 messages (up to 5 conversation turns)
    recent_history = valid_history[-10:]

    # Format history for LLM prompt
    formatted_history = []
    for msg in recent_history:
        role = "User" if msg.get("role") in ("user", "human") else "Assistant"
        formatted_history.append(f"{role}: {msg.get('content').strip()}")
    
    history_str = "\n".join(formatted_history)

    system_instruction = (
        "You are an expert query understanding system for a PDF document RAG assistant. "
        "Your task is to rephrase the user's latest question into a self-contained, standalone search query for document retrieval.\n\n"
        "RULES:\n"
        "1. If the current question is already standalone, clear, and complete on its own (e.g. 'What are the company's financial risks?'), preserve and return the original question EXACTLY.\n"
        "2. If the current question is a follow-up, incomplete, or contains pronouns/ellipsis (e.g. 'What about 2023?', 'How does it work?', 'Compare that to profit', 'Why did you say that?', 'Tell me more about the second point'), rewrite it into a complete, explicit standalone retrieval query using context from previous messages.\n"
        "3. If the user question specifically asks about the conversation itself (e.g. 'What was the first question I asked you?', 'Summarize our conversation so far'), preserve the conversational question clearly so the dialogue history can answer it.\n"
        "4. If the user question introduces a brand new, independent, or unrelated topic compared to previous messages, DO NOT let previous conversation context affect it. Preserve the original question.\n"
        "5. Do NOT answer the question. Return ONLY the rewritten retrieval query text without explanations, quotes, or preambles."
    )

    user_prompt = f"""Recent Conversation History:
{history_str}

Latest User Question:
"{clean_question}"

Standalone Retrieval Query:"""

    try:
        client = get_groq_client()
        model_name = get_groq_model()

        response = execute_groq_completion_with_retry(
            client,
            model=model_name,
            max_tokens=150,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ]
        )

        retrieval_query = response.choices[0].message.content or ""
        # Strip thinking tags if present from thinking models
        if "<think>" in retrieval_query:
            retrieval_query = re.sub(r"<think>.*?</think>", "", retrieval_query, flags=re.DOTALL)
        retrieval_query = retrieval_query.strip().strip('"').strip("'")

        if not retrieval_query:
            retrieval_query = clean_question

        log_query_rewriting(clean_question, retrieval_query)
        return retrieval_query

    except Exception as e:
        safe_print(f"[Query Rewriter Warning]: Failed to call Groq ({str(e)}). Falling back to original question.")
        log_query_rewriting(clean_question, clean_question)
        return clean_question
