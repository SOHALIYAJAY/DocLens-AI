import json
import os
import re
from services.llm_service import get_groq_vision_client

def analyze_image(image_base64: str, image_format: str = "jpeg", prompt: str = None) -> dict:
    """
    Generates a structured explanation of an image using Groq Vision.
    Uses GROQ_VISION_API_KEY exclusively for vision analysis tasks.
    
    Args:
        image_base64 (str): The base64 encoded image string.
        image_format (str): The format of the image (e.g. png, jpeg).
        prompt (str, optional): Additional user context or question about the image.
        
    Returns:
        dict: A dictionary matching the ImageExplanationResponse schema.
    """
    if not image_base64:
        raise ValueError("No image provided.")
        
    client = get_groq_vision_client()
    
    # Candidate vision models supported by Groq
    primary_model = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")
    candidate_models = [primary_model, "qwen/qwen3.6-27b", "qwen/qwen3.8-27b"]
    # De-duplicate while preserving order
    vision_models = list(dict.fromkeys(candidate_models))

    system_instruction = (
        "You are an expert at analyzing images, diagrams, charts, and figures found in PDF documents. "
        "Identify whether the image is a: Diagram, Flowchart, Graph, Chart, Architecture Diagram, "
        "UML Diagram, Scientific Figure, Table, or Screenshot. "
        "CRITICAL INSTRUCTION: Provide medium-sized, concise explanations only. Avoid long walls of text, multi-paragraph explanations, or overly verbose descriptions. "
        "Keep all fields short, clear, and direct.\n"
        "You must respond ONLY with a valid JSON object matching the following structure exactly:\n"
        "{\n"
        '  "title": "A short, concise title (max 6 words)",\n'
        '  "summary": "A clear 1-2 sentence medium-sized summary of what the image shows",\n'
        '  "explanation": "A concise medium-sized explanation (2-3 sentences max) detailing the contents and key concepts. Keep it focused and brief.",\n'
        '  "important_components": ["Component 1 (short)", "Component 2 (short)"],\n'
        '  "relationships": ["Short relationship or flow description"],\n'
        '  "key_takeaways": ["Takeaway 1 (short)", "Takeaway 2 (short)"],\n'
        '  "real_world_application": "Short 1-sentence application (or empty string if not applicable)"\n'
        "}\n"
        "Do not include any markdown formatting like ```json or outside text. "
        "Do NOT output any <think> or reasoning tags. Begin your response immediately with the opening brace '{'."
    )

    user_text = "Please analyze this image and provide a concise, medium-sized structured explanation. Keep explanations focused, direct, and avoid large text."
    if prompt:
        user_text += f" Additional context/question from user: {prompt}"

    fmt = image_format.lower()
    if fmt == "jpg":
        fmt = "jpeg"

    last_error = None
    for model_name in vision_models:
        try:
            print(f"=== EXPLAINING IMAGE VIA GROQ VISION ({model_name}) ===")
            response = client.chat.completions.create(
                model=model_name,
                max_tokens=500,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{fmt};base64,{image_base64}"
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
            
            # Clean reasoning tags <think>...</think> if present from reasoning models
            clean_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()
            
            # Clean markdown code blocks
            if "```" in clean_text:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean_text, re.DOTALL)
                if match:
                    clean_text = match.group(1)
                else:
                    clean_text = clean_text.replace("```json", "").replace("```", "").strip()
            
            # Fallback regex to extract JSON object
            json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(0)

            result_dict = json.loads(clean_text)
            print("=== IMAGE EXPLANATION GENERATED SUCCESSFULLY ===")
            return result_dict

        except json.JSONDecodeError as json_err:
            print(f"Failed to parse JSON from Groq Vision ({model_name}): {raw_text}")
            last_error = f"Model {model_name} did not return valid JSON: {str(json_err)}"
        except Exception as e:
            print(f"Vision model {model_name} failed: {str(e)}")
            last_error = str(e)

    raise Exception(f"An unexpected error occurred during analyze_image via Groq Vision: {last_error}")

