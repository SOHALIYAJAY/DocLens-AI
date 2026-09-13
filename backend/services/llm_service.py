import os
import re
import time
import groq
from groq import Groq
from dotenv import load_dotenv
from typing import List

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(override=True)

from services.token_service import count_tokens
from services.chunk_service import chunk_text_by_tokens
from services.rate_limiter_service import groq_rate_limiter


def safe_print(*args, **kwargs):
    """Prints text safely without throwing UnicodeEncodeError on Windows terminals (CP1252)."""
    try:
        print(*args, **kwargs)
    except Exception:
        try:
            clean_args = [str(a).encode("ascii", errors="replace").decode("ascii") for a in args]
            print(*clean_args, **kwargs)
        except Exception:
            pass


def extract_retry_wait_time(e: Exception) -> float:
    """
    Attempts to extract the server-provided wait/retry duration in seconds from a Groq rate-limit exception.
    Checks response HTTP headers first, then falls back to regex matching on exception text message.
    """
    if hasattr(e, "response") and e.response is not None:
        headers = getattr(e.response, "headers", {})
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

    msg = str(e)
    match_sec = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", msg, re.IGNORECASE)
    if match_sec:
        return float(match_sec.group(1))

    match_min_sec = re.search(r"try again in (\d+)m(\d+(?:\.\d+)?)s", msg, re.IGNORECASE)
    if match_min_sec:
        return float(match_min_sec.group(1)) * 60.0 + float(match_min_sec.group(2))

    return None


def is_rate_limit_error(e: Exception) -> bool:
    """Checks if an exception is a Groq 429 Rate Limit error."""
    if isinstance(e, groq.RateLimitError):
        return True
    if isinstance(e, groq.APIStatusError) and getattr(e, "status_code", None) == 429:
        return True
    
    status_code = getattr(e, "status_code", None)
    if status_code == 429:
        return True

    msg = str(e).lower()
    return "429" in msg or "rate limit" in msg or "rate_limit_exceeded" in msg


def execute_groq_completion_with_retry(client: Groq, **kwargs):
    """
    Executes a Groq chat completion request with token-aware retry logic for HTTP 429 rate limits.
    
    - Detects 429 Rate Limit exceptions.
    - Reads server-provided retry-after duration when available.
    - Uses exponential backoff (2s, 4s, 8s...) when server duration is unavailable.
    - Retries up to MAX_RETRIES (default: 3) times.
    - Logs each retry attempt clearly.
    - Raises a clear descriptive error if all retries fail.
    """
    max_retries = int(os.getenv("GROQ_MAX_RETRIES", "3"))
    initial_backoff = float(os.getenv("GROQ_INITIAL_BACKOFF", "2.0"))

    for attempt in range(1, max_retries + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            is_conn_err = isinstance(e, groq.APIConnectionError) or "connection error" in str(e).lower() or "getaddrinfo" in str(e).lower()
            if not (is_rate_limit_error(e) or is_conn_err):
                raise e

            # Model Fallback Mechanism for Rate Limit / TPD Exhaustion
            if is_rate_limit_error(e):
                current_model = kwargs.get("model", get_groq_model())
                fallbacks = ["groq/compound-mini", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "groq/compound"]
                if current_model not in fallbacks:
                    fallbacks.insert(0, current_model)
                idx = fallbacks.index(current_model) if current_model in fallbacks else 0
                for fallback_model in fallbacks[idx + 1:]:
                    print(f"[Groq Fallback] Rate limit on '{current_model}'. Switching to '{fallback_model}'...")
                    try:
                        fallback_kwargs = dict(kwargs)
                        fallback_kwargs["model"] = fallback_model
                        res = client.chat.completions.create(**fallback_kwargs)
                        return res
                    except Exception as fb_err:
                        if not is_rate_limit_error(fb_err):
                            break

            if attempt >= max_retries:
                print(f"[Groq Error] Exception persists after {max_retries} retries. Request failed.")
                raise Exception(
                    f"Groq API error after {max_retries} retries: {str(e)}"
                ) from e

            if is_conn_err:
                wait_seconds = 3.0 * attempt
                print(f"[Groq Connection Error] Network glitch on attempt {attempt}/{max_retries}. Retrying in {wait_seconds:.1f}s...")
                time.sleep(wait_seconds)
                continue

            server_wait = extract_retry_wait_time(e)
            if server_wait is not None and server_wait > 0:
                if server_wait > 10.0:
                    server_wait = 10.0
                wait_seconds = server_wait + 0.2
                log_msg = f"[Groq 429] Rate limit hit on attempt {attempt}/{max_retries}. Retrying in {wait_seconds:.1f}s..."
            else:
                wait_seconds = initial_backoff * (2 ** (attempt - 1))
                log_msg = f"[Groq 429] Rate limit hit on attempt {attempt}/{max_retries}. Retrying in {wait_seconds:.1f}s (exponential backoff)..."

            print(log_msg)
            time.sleep(wait_seconds)


def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing in the .env file. Please add it.")
        
    return Groq(api_key=api_key)

def get_groq_vision_client() -> Groq:
    api_key = os.getenv("GROQ_VISION_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_VISION_API_KEY is missing in the .env file. Please add it.")
        
    return Groq(api_key=api_key)

def get_groq_model() -> str:
    return os.getenv("GROQ_MODEL", "groq/compound-mini")

# Aliases for backwards compatibility
def get_agentrouter_client() -> Groq:
    return get_groq_client()

def get_claude_model() -> str:
    return get_groq_model()


def generate_response(
    context_chunks: List[str], 
    question: str, 
    history: Optional[List[dict]] = None
) -> str:
    """
    Generates a highly accurate, grounded response using Groq AI.
    It strictly uses ONLY the provided context chunks and runs through Grounding & Hallucination verification.
    
    Args:
        context_chunks (List[str]): The relevant text chunks retrieved from the vector database, table service, or visual service.
        question (str): The specific question the user asked about the PDF.
        history (Optional[List[dict]]): Recent conversation history messages.
        
    Returns:
        str: The generated answer from the AI.
        
    Raises:
        ValueError: If inputs are invalid or the API key is missing.
        Exception: If the API request fails.
    """
    if not context_chunks:
        raise ValueError("No context chunks provided. Cannot generate a response.")
        
    if not question or not question.strip():
        raise ValueError("The user question is empty. Please ask a valid question.")

    try:
        from services.grounding_service import generate_grounded_response
        return generate_grounded_response(
            context_chunks=context_chunks,
            question=question,
            history=history
        )
    except Exception as e:
        raise Exception(f"An unexpected error occurred during generate_response via Groq: {str(e)}")




def reduce_summaries_hierarchically(
    summaries: List[str],
    summary_type: str,
    system_instruction: str,
    client: Groq,
    model_name: str,
    max_reduce_tokens: int = None
) -> str:
    """
    Hierarchically reduces a list of chunk summaries into a single final summary.
    If the combined token count of summaries exceeds max_reduce_tokens, groups them
    into intermediate batches and synthesizes intermediate summaries recursively
    until the combined size fits safely within a single final Groq request.
    """
    if max_reduce_tokens is None:
        max_reduce_tokens = int(os.getenv("GROQ_MAX_REDUCE_TOKENS", "6000"))

    current_summaries = list(summaries)
    level = 1

    while True:
        combined_text = "\n\n".join(
            [f"--- Section {i+1} Summary ---\n{s}" for i, s in enumerate(current_summaries)]
        )
        combined_tokens = count_tokens(combined_text)
        print(f"Combined summaries token count: {combined_tokens} (max single-prompt limit: {max_reduce_tokens})")

        # Base case: combined text fits within limit or only 1 summary left
        if combined_tokens <= max_reduce_tokens or len(current_summaries) <= 1:
            print("Generating final summary")
            final_prompt = f"""
Below are the section summaries extracted from a large PDF document in order:
<section_summaries>
{combined_text}
</section_summaries>

Please provide a final {summary_type} summary of the entire document based on these section summaries.
"""
            est_tokens = count_tokens(system_instruction) + count_tokens(final_prompt) + 2048
            groq_rate_limiter.wait_for_capacity(est_tokens)

            final_response = execute_groq_completion_with_retry(
                client,
                model=model_name,
                max_tokens=2048,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": final_prompt}
                ]
            )
            return final_response.choices[0].message.content or ""

        # Hierarchical reduction step: group summaries into batches within max_reduce_tokens
        groups = []
        current_group = []
        current_group_tokens = 0

        for summary in current_summaries:
            summary_tokens = count_tokens(summary)
            if current_group and (current_group_tokens + summary_tokens > max_reduce_tokens):
                groups.append(current_group)
                current_group = [summary]
                current_group_tokens = summary_tokens
            else:
                current_group.append(summary)
                current_group_tokens += summary_tokens

        if current_group:
            groups.append(current_group)

        safe_print(f"Hierarchical reduction level {level}: grouped {len(current_summaries)} summaries into {len(groups)} intermediate groups")

        intermediate_system_prompt = (
            "You are an expert summarization AI synthesizing section summaries from a large document. "
            "Combine and condense the section summaries into a unified, structured, and coherent intermediate summary. "
            "ACCURACY REQUIREMENTS:\n"
            "- PRESERVE ALL NUMERICAL DATA: Retain exact statistics, percentages, dates, and key metrics.\n"
            "- PRESERVE RESEARCH FLOW: Maintain logical connections between methodology, findings, results, conclusions, and limitations.\n"
            "- PRESERVE SECTION RELATIONSHIPS: Keep structural hierarchy and cross-section context clear."
        )

        intermediate_summaries = []
        for g_idx, group in enumerate(groups, 1):
            safe_print(f"Processing intermediate group {g_idx}/{len(groups)} (level {level})")
            group_text = "\n\n".join(
                [f"--- Section {i+1} Summary ---\n{s}" for i, s in enumerate(group)]
            )
            intermediate_user_prompt = f"""
Please synthesize and summarize the following section summaries:
<group_summaries>
{group_text}
</group_summaries>
"""
            est_tokens = count_tokens(intermediate_system_prompt) + count_tokens(intermediate_user_prompt) + 1500
            groq_rate_limiter.wait_for_capacity(est_tokens)

            group_response = execute_groq_completion_with_retry(
                client,
                model=model_name,
                max_tokens=1500,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": intermediate_system_prompt},
                    {"role": "user", "content": intermediate_user_prompt}
                ]
            )
            inter_summary = group_response.choices[0].message.content or ""
            intermediate_summaries.append(inter_summary)

        current_summaries = intermediate_summaries
        level += 1


def generate_summary(pdf_text: str, summary_type: str) -> str:
    """
    Generates a high-quality summary of the provided PDF text using Groq AI.
    For small PDFs, uses single-request summarization.
    For large PDFs, chunks the document, summarizes each chunk, and combines them into a final summary.
    
    Args:
        pdf_text (str): The extracted text from the PDF document.
        summary_type (str): The requested size/detail of the summary (small, medium, large).
        
    Returns:
        str: The generated summary.
        
    Raises:
        ValueError: If inputs are invalid or the API key is missing.
        Exception: If the API request fails.
    """
    
    if not pdf_text or not pdf_text.strip():
        raise ValueError("The provided PDF text is empty. Cannot generate a summary.")
        
    valid_types = ["small", "medium", "large"]
    if summary_type not in valid_types:
        raise ValueError(f"Invalid summary_type. Must be one of: {', '.join(valid_types)}")

    try:
        # 1. Initialize Groq Client & Model
        client = get_groq_client()
        model_name = get_groq_model()

        # 2. Dynamic System Instructions based on summary_type
        base_instruction = (
            "You are an expert summarization AI specializing in technical, financial, academic, and business PDF documents. "
            "Your ONLY job is to summarize the provided PDF text accurately based strictly on the text provided. "
            "Do NOT use outside knowledge. Do NOT hallucinate. "
            "ACCURACY GUIDELINES:\n"
            "1. PRESERVE NUMBERS & METRICS: Retain all critical numbers, statistics, percentages, dates, dollar amounts, and quantitative results.\n"
            "2. PRESERVE RESEARCH & FINDINGS: Explicitly capture methodology, main findings, experimental/analytical results, key conclusions, and limitations.\n"
            "3. PRESERVE SECTION CONTEXT: Maintain logical flow, topic continuity, and relationships between sections.\n"
        )
        
        style_instruction = ""
        if summary_type == "small":
            style_instruction = (
                "Create a small summary: Provide 3-5 bullet points focusing ONLY on the most important ideas. "
                "Keep the total length under 100 words."
            )
        elif summary_type == "medium":
            style_instruction = (
                "Create a medium summary: Write around 200-300 words explaining the important concepts with some details. "
                "Use bullet points where appropriate."
            )
        elif summary_type == "large":
            style_instruction = (
                "Create a large summary: Write around 500-700 words covering all major topics from the PDF. "
                "Use headings, subheadings, and bullet points to maintain logical flow. Preserve important technical terms."
            )
            
        system_instruction = base_instruction + style_instruction

        # 3. Token Count & Chunking Decision
        total_tokens = count_tokens(pdf_text)
        safe_print(f"PDF token count: {total_tokens}")

        # Target 6,500 tokens per chunk with 400 overlap
        chunks = chunk_text_by_tokens(pdf_text, max_tokens_per_chunk=6500, overlap_tokens=400)
        num_chunks = len(chunks)
        safe_print(f"Created {num_chunks} chunks")

        # 4. SINGLE-REQUEST FLOW for small PDFs (1 chunk)
        if num_chunks <= 1:
            safe_print("Processing chunk 1/1")
            prompt = f"""
Please provide a {summary_type} summary of the following text extracted from a PDF document:
<pdf_text>
{pdf_text}
</pdf_text>
"""
            est_tokens = count_tokens(system_instruction) + count_tokens(prompt) + 2048
            groq_rate_limiter.wait_for_capacity(est_tokens)

            response = execute_groq_completion_with_retry(
                client,
                model=model_name,
                max_tokens=2048,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ]
            )
            final_text = response.choices[0].message.content or ""
            safe_print("=== SUMMARY GENERATED SUCCESSFULLY ===\n")
            return final_text

        # 5. MAP-REDUCE CHUNKED FLOW for large PDFs (>1 chunks)
        chunk_summaries = []
        chunk_system_prompt = (
            "You are an expert summarization AI. Summarize this section of a PDF document concisely and accurately. "
            "ACCURACY REQUIREMENTS:\n"
            "- Extract key concepts, section headings/topics, methodology, research findings, results, conclusions, and limitations.\n"
            "- PRESERVE EXACT NUMBERS: Keep all quantitative metrics, statistics, percentages, dates, and measurements intact.\n"
            "- PRESERVE CONTINUITY: Retain paragraph structure and relationships between ideas.\n"
            "- DO NOT HALLUCINATE: Base your summary strictly on the provided section text."
        )

        for idx, chunk in enumerate(chunks, 1):
            safe_print(f"Processing chunk {idx}/{num_chunks}")
            chunk_user_prompt = f"""
Please summarize the following section from a PDF document:
<pdf_section>
{chunk}
</pdf_section>
"""
            est_tokens = count_tokens(chunk_system_prompt) + count_tokens(chunk_user_prompt) + 1500
            groq_rate_limiter.wait_for_capacity(est_tokens)

            chunk_response = execute_groq_completion_with_retry(
                client,
                model=model_name,
                max_tokens=1500,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": chunk_system_prompt},
                    {"role": "user", "content": chunk_user_prompt}
                ]
            )
            summary_text = chunk_response.choices[0].message.content or ""
            chunk_summaries.append(summary_text)

        # 6. HIERARCHICAL REDUCTION STAGE for combining chunk summaries
        final_text = reduce_summaries_hierarchically(
            summaries=chunk_summaries,
            summary_type=summary_type,
            system_instruction=system_instruction,
            client=client,
            model_name=model_name
        )
        safe_print("=== SUMMARY GENERATED SUCCESSFULLY ===\n")
        return final_text

    except Exception as e:
        raise Exception(f"An unexpected error occurred during generate_summary via Groq: {str(e)}")


