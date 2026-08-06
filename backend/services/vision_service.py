# services/vision_service.py
import json
from anthropic import APIError, APIConnectionError
from services.llm_service import get_agentrouter_client, get_claude_model

def analyze_image(image_base64: str, image_format: str = "jpeg", prompt: str = None) -> dict:
    """
    Generates a structured explanation of an image using Claude Vision.
    
    Args:
        image_base64 (str): The base64 encoded image string.
        image_format (str): The format of the image (e.g. png, jpeg).
        prompt (str, optional): Additional user context or question about the image.
        
    Returns:
        dict: A dictionary matching the ImageExplanationResponse schema.
    """
    if not image_base64:
        raise ValueError("No image provided.")
        
    try:
        client = get_agentrouter_client()
        model_name = get_claude_model()
        
        system_instruction = (
            "You are an expert at analyzing images, diagrams, charts, and figures found in PDF documents. "
            "Identify whether the image is a: Diagram, Flowchart, Graph, Chart, Architecture Diagram, "
            "UML Diagram, Scientific Figure, Table, or Screenshot. "
            "You must respond ONLY with a valid JSON object matching the following structure exactly:\n"
            "{\n"
            '  "title": "A short, descriptive title",\n'
            '  "summary": "A 1-2 sentence summary of what the image shows",\n'
            '  "explanation": "A detailed explanation of the image contents, data, or concepts",\n'
            '  "important_components": ["Component 1", "Component 2"],\n'
            '  "relationships": ["Relationship between X and Y", "How A flows to B"],\n'
            '  "key_takeaways": ["Takeaway 1", "Takeaway 2"],\n'
            '  "real_world_application": "How this concept applies in the real world (if applicable, else empty string)"\n'
            "}\n"
            "Do not include any markdown formatting like ```json or outside text. Just the raw JSON object."
        )
        
        user_text = "Please analyze this image and provide a structured explanation. check image carefully"
        if prompt:
            user_text += f" Additional context/question from user: {prompt}"
            
        print("=== EXPLAINING IMAGE ===")
        
        response = client.messages.create(
            model=model_name,
            max_tokens=2048,
            temperature=0.2,
            system=system_instruction,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": f"image/{image_format.lower()}",
                                "data": image_base64
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
        
        final_text = ""
        for block in response.content:
            if getattr(block, "type", "") == "text":
                final_text += block.text
                
        # Parse the JSON response
        try:
            # Clean up the response in case Claude added markdown code blocks
            clean_json = final_text.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
                
            result_dict = json.loads(clean_json.strip())
            print("=== IMAGE EXPLANATION GENERATED SUCCESSFULLY ===")
            return result_dict
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON from Claude: {final_text}")
            raise Exception("AI did not return valid JSON.")
            
    except APIConnectionError as e:
        raise Exception(f"Failed to connect to AgentRouter API for vision: {str(e)}")
    except APIError as e:
        raise Exception(f"AgentRouter API returned an error for vision: {str(e)}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred during analyze_image: {str(e)}")
