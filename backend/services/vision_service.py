import json
import os
import io
import re
import time
import base64
import random
import requests
from PIL import Image
from services.llm_service import get_groq_vision_client, get_groq_client, safe_print, extract_retry_wait_time

def _prepare_image_for_vision(image_base64: str, image_format: str = "jpeg") -> tuple[str, str]:
    """
    Optimizes the image for Groq Vision:
    - Downscales oversized images to max dimension 1024px while preserving clarity.
    - Converts transparency (RGBA/Palette) to clean white RGB background.
    - Encodes as optimized JPEG to avoid massive payload bursts that trigger Groq 503 Over Capacity.
    """
    try:
        raw_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(raw_bytes))

        # Convert RGBA / P / LA modes to clean RGB
        if img.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                bg.paste(img, mask=img.split()[3])
            else:
                converted = img.convert("RGBA")
                bg.paste(converted, mask=converted.split()[3])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Downscale if oversized to keep payload lightweight for Groq LPUs
        max_dim = 1024
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            new_w, new_h = max(2, int(w * scale)), max(2, int(h * scale))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        optimized_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return optimized_b64, "jpeg"
    except Exception as e:
        safe_print(f"[Vision Service] Image optimization note: {e}")
        return image_base64, image_format


def _parse_vision_response(raw_text: str) -> dict:
    """
    Safely parses JSON from the vision model response, with regex fallbacks
    to handle markdown fences, thinking tags, or minor formatting issues.
    """
    clean_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()

    if "```" in clean_text:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean_text, re.DOTALL)
        if match:
            clean_text = match.group(1).strip()
        else:
            clean_text = clean_text.replace("```json", "").replace("```", "").strip()

    json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
    if json_match:
        clean_text = json_match.group(0).strip()

    try:
        data = json.loads(clean_text)
        if isinstance(data, dict):
            return {
                "title": data.get("title") or "Image Analysis",
                "summary": data.get("summary") or "",
                "explanation": data.get("explanation") or "",
                "key_takeaways": data.get("key_takeaways") or [],
                "important_components": data.get("important_components") or [],
                "relationships": data.get("relationships") or [],
                "real_world_application": data.get("real_world_application") or ""
            }
    except Exception:
        pass

    title_m = re.search(r'"title"\s*:\s*"([^"]+)"', clean_text)
    summary_m = re.search(r'"summary"\s*:\s*"([^"]+)"', clean_text)
    expl_m = re.search(r'"explanation"\s*:\s*"([^"]+)"', clean_text)
    takeaways_m = re.findall(r'"key_takeaways"\s*:\s*\[(.*?)\]', clean_text, re.DOTALL)
    takeaways = []
    if takeaways_m:
        takeaways = [t.strip().strip('"').strip("'") for t in takeaways_m[0].split(",") if t.strip()]

    fallback_summary = summary_m.group(1) if summary_m else (clean_text[:200] + "..." if len(clean_text) > 200 else clean_text)

    return {
        "title": title_m.group(1) if title_m else "Image Analysis",
        "summary": fallback_summary,
        "explanation": expl_m.group(1) if expl_m else fallback_summary,
        "key_takeaways": takeaways[:3],
        "important_components": [],
        "relationships": [],
        "real_world_application": ""
    }


def _analyze_image_with_gemini(
    gemini_key: str,
    opt_base64: str,
    opt_format: str,
    user_text: str,
    system_instruction: str
) -> dict:
    """
    Explains an image using Google Gemini Vision API via direct REST call.
    Uses candidate models with automatic failover (gemini-3-flash-preview, gemini-3.6-flash, gemini-3.1-flash-lite).
    """
    fmt = opt_format.lower()
    if fmt in ("jpg", "jpeg"):
        mime_type = "image/jpeg"
    elif fmt == "png":
        mime_type = "image/png"
    elif fmt == "webp":
        mime_type = "image/webp"
    else:
        mime_type = f"image/{fmt}"

    candidate_models = [
        os.getenv("GEMINI_VISION_MODEL", "gemini-3-flash-preview"),
        "gemini-3-flash-preview",
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash"
    ]
    gemini_models = list(dict.fromkeys([m for m in candidate_models if m]))

    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "parts": [
                    {"text": user_text},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": opt_base64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2
        }
    }

    last_gemini_error = None
    for model_name in gemini_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        safe_print(f"=== EXPLAINING IMAGE VIA GEMINI VISION (Model: {model_name}) ===")
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                result_dict = _parse_vision_response(raw_text)
                safe_print(f"=== GEMINI VISION EXPLANATION GENERATED SUCCESSFULLY ({model_name}) ===")
                return result_dict

            err_msg = resp.text
            safe_print(f"[Gemini Vision Warning] Model '{model_name}' returned status {resp.status_code}: {err_msg[:120]}")
            last_gemini_error = f"Status {resp.status_code}: {err_msg[:150]}"

            # On high demand (503) or rate limit (429), try next model candidate
            if resp.status_code in (429, 503):
                time.sleep(0.5)
                continue
        except Exception as ex:
            safe_print(f"[Gemini Vision Warning] Request to {model_name} failed: {ex}")
            last_gemini_error = str(ex)

    raise Exception(f"Gemini Vision failed across candidate models: {last_gemini_error}")


def analyze_image(image_base64: str, image_format: str = "jpeg", prompt: str = None) -> dict:
    """
    Generates a medium-sized structured explanation of an image using Gemini Vision AI
    (with secondary fallback to Groq Vision).
    """
    if not image_base64:
        raise ValueError("No image provided for analysis.")

    # 1. Optimize image payload (downscale to max 1024px & compress to JPEG)
    opt_base64, opt_format = _prepare_image_for_vision(image_base64, image_format)

    system_instruction = (
        "You are an expert at analyzing images, diagrams, charts, and figures found in documents. "
        "CRITICAL LENGTH INSTRUCTION: Provide a medium-sized, concise explanation. "
        "Do NOT output large walls of text, multi-paragraph essays, or overly verbose descriptions. "
        "Keep the explanation strictly medium-sized, crisp, and direct.\n"
        "Respond ONLY with a valid JSON object matching the following structure:\n"
        "{\n"
        '  "title": "A clear, concise title (max 6-8 words)",\n'
        '  "summary": "A clear 1-2 sentence medium-sized summary of what the image shows",\n'
        '  "explanation": "A concise medium-sized explanation (2-3 sentences max) detailing the contents, data points, or key concept shown without large text",\n'
        '  "key_takeaways": ["Takeaway 1 (concise)", "Takeaway 2 (concise)", "Takeaway 3 (concise)"],\n'
        '  "important_components": ["Component 1", "Component 2"],\n'
        '  "real_world_application": "One short sentence on practical application (or empty string)"\n'
        "}\n"
        "Do not include markdown code block formatting like ```json or any outside commentary. "
        "Do NOT output any <think> tags. Start directly with the opening brace '{'."
    )

    user_text = "Please analyze this image and provide a medium-sized, clear, structured explanation. Keep explanations focused and avoid large walls of text."
    if prompt:
        user_text += f" User question / focus: {prompt}"

    # 2. Check and prioritize Gemini Vision API
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip() or "AQ.Ab8RN6IM9WtdCRHd553svuIdG7W2-I0vcrIc2tmMPbwMUlE-dA"
    if gemini_key:
        try:
            return _analyze_image_with_gemini(
                gemini_key=gemini_key,
                opt_base64=opt_base64,
                opt_format=opt_format,
                user_text=user_text,
                system_instruction=system_instruction
            )
        except Exception as gemini_err:
            safe_print(f"[Vision Service] Gemini Vision encounter: {gemini_err}. Attempting Groq Vision fallback...")

    # 3. Secondary Fallback: Groq Vision
    clients = []
    try:
        clients.append(get_groq_vision_client())
    except Exception as e:
        safe_print(f"[Vision Service] Could not init vision client: {e}")

    try:
        fallback_client = get_groq_client()
        if not clients or fallback_client.api_key != clients[0].api_key:
            clients.append(fallback_client)
    except Exception:
        pass

    if not clients:
        raise ValueError("No valid Vision API key found. Please check GEMINI_API_KEY or GROQ_VISION_API_KEY in .env.")

    # Candidate vision models supported by Groq
    primary_model = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    candidate_models = [primary_model, "qwen/qwen3.8-27b"]
    vision_models = list(dict.fromkeys(candidate_models))

    max_retries = int(os.getenv("GROQ_MAX_RETRIES", "3"))
    last_error = None
    is_temporary_error = False

    for client_idx, client in enumerate(clients):
        for model_name in vision_models:
            for attempt in range(1, max_retries + 1):
                try:
                    safe_print(f"=== EXPLAINING IMAGE VIA GROQ VISION (Model: {model_name}, Client: {client_idx + 1}/{len(clients)}, Attempt: {attempt}/{max_retries}) ===")
                    response = client.chat.completions.create(
                        model=model_name,
                        max_tokens=1024,
                        temperature=0.2,
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/{opt_format};base64,{opt_base64}"
                                        }
                                    },
                                    {
                                        "type": "text",
                                        "text": user_text
                                    }
                                ]
                            }
                        ]
                    )

                    raw_text = response.choices[0].message.content or ""
                    result_dict = _parse_vision_response(raw_text)
                    safe_print("=== IMAGE EXPLANATION GENERATED SUCCESSFULLY ===")
                    return result_dict

                except Exception as e:
                    err_str = str(e)
                    last_error = err_str
                    safe_print(f"[Vision Warning] Attempt {attempt}/{max_retries} failed on {model_name}: {err_str}")

                    # Check if error is transient (503 Over Capacity, 429 Rate Limit, or Connection Glitch)
                    status_code = getattr(e, "status_code", None)
                    is_over_capacity = status_code == 503 or "503" in err_str or "over capacity" in err_str.lower()
                    is_rate_limited = status_code == 429 or "429" in err_str or "rate limit" in err_str.lower()
                    is_connection_err = "connection" in err_str.lower() or "timeout" in err_str.lower()

                    if is_over_capacity or is_rate_limited or is_connection_err:
                        is_temporary_error = True
                        if attempt < max_retries:
                            # If server provides Retry-After, respect it; otherwise use exponential backoff (~5s on attempt 1, ~10s on attempt 2) with jitter
                            server_wait = extract_retry_wait_time(e)
                            if server_wait is not None and server_wait > 0:
                                wait_seconds = server_wait + random.uniform(0.1, 0.5)
                            else:
                                base_delay = 5.0 * (2 ** (attempt - 1))
                                jitter = random.uniform(0.1, 0.8)
                                wait_seconds = base_delay + jitter

                            safe_print(f"[Vision Backoff] Groq server busy (503/429). Retrying in {wait_seconds:.1f}s...")
                            time.sleep(wait_seconds)
                        else:
                            # 3 attempts exhausted on temporary error
                            break
                    else:
                        # Non-transient error: do not retry this client/model
                        break

            # If 503 over capacity or 429 persisted across all 3 attempts, avoid redundant retry loops
            if is_temporary_error and attempt >= max_retries:
                break
        if is_temporary_error and attempt >= max_retries:
            break

    if is_temporary_error:
        raise Exception("Image analysis service is temporarily busy. Please try again in a moment.")

    raise Exception(f"Vision analysis failed: {last_error}")
