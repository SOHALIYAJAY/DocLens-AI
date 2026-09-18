# api/image.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from models.schemas import ExplainImageRequest, ImageExplanationResponse
from services.image_service import get_image
from services.vision_service import analyze_image

router = APIRouter()

@router.get("/image/{image_id}")
async def get_image_endpoint(image_id: str):
    """
    Endpoint to retrieve an extracted image by its ID.
    Returns the raw image bytes with the appropriate content type.
    """
    image_data = get_image(image_id)
    if not image_data:
        raise HTTPException(status_code=404, detail="Image not found")
        
    media_type = f"image/{image_data['format'].lower()}"
    return Response(content=image_data['bytes'], media_type=media_type)

@router.post("/image/explain", response_model=ImageExplanationResponse)
@router.post("/image/explain/", response_model=ImageExplanationResponse)
@router.post("/explain-image", response_model=ImageExplanationResponse)
@router.post("/explain-image/", response_model=ImageExplanationResponse)
async def explain_image_endpoint(request: ExplainImageRequest):
    """
    Endpoint to explain a specific image using Vision AI.
    """
    image_data = None
    if request.image_id:
        image_data = get_image(request.image_id)
        
    if not image_data and request.image_base64:
        image_data = {
            "base64_data": request.image_base64,
            "format": request.image_format or "jpeg"
        }
        
    if not image_data:
        raise HTTPException(
            status_code=404, 
            detail=f"Image '{request.image_id}' not found in active session or cache. Please re-upload or re-extract images from the PDF."
        )
        
    try:
        result = analyze_image(
            image_base64=image_data["base64_data"], 
            image_format=image_data["format"], 
            prompt=request.prompt
        )
        return ImageExplanationResponse(
            success=True,
            title=result.get("title", "Image Analysis"),
            summary=result.get("summary", ""),
            explanation=result.get("explanation", ""),
            important_components=result.get("important_components", []),
            relationships=result.get("relationships", []),
            key_takeaways=result.get("key_takeaways", []),
            real_world_application=result.get("real_world_application", "")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
