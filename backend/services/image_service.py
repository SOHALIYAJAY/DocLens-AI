# services/image_service.py
import fitz  # PyMuPDF
import base64
import uuid

# Global in-memory store for images. 
# Maps image_id (str) to a dict containing {"base64_data": str, "format": str, "bytes": bytes}
IMAGE_STORE = {}

def extract_and_store_images(file_bytes: bytes) -> list[dict]:
    """
    Extracts all images from a PDF file using PyMuPDF and stores them in IMAGE_STORE.
    
    Args:
        file_bytes (bytes): The raw bytes of the uploaded PDF file.
        
    Returns:
        list[dict]: A list of dictionaries containing image metadata (image_id, page, format).
    """
    try:
        extracted_images = []
        
        # Open PDF from bytes
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # get_images() returns a list of image instances on the page
            images = page.get_images(full=True)
            
            for img_index, img in enumerate(images):
                xref = img[0]
                
                # Extract image bytes and extension
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Convert image bytes to base64
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                
                # Generate unique ID for the image
                image_id = str(uuid.uuid4())
                
                # Store in global dictionary
                IMAGE_STORE[image_id] = {
                    "base64_data": image_base64,
                    "format": image_ext,
                    "bytes": image_bytes
                }
                
                extracted_images.append({
                    "image_id": image_id,
                    "page": page_num + 1,
                    "image_index": img_index + 1,
                    "format": image_ext
                })
                
        doc.close()
        return extracted_images
        
    except Exception as e:
        print(f"Failed to extract images from PDF: {str(e)}")
        # Don't fail the whole PDF upload if image extraction fails, just return empty list
        return []

def get_image(image_id: str) -> dict:
    """
    Retrieves an image from the global store.
    
    Args:
        image_id (str): The ID of the image to retrieve.
        
    Returns:
        dict: A dictionary containing the image bytes and format, or None if not found.
    """
    return IMAGE_STORE.get(image_id)

def get_image_base64(image_id: str) -> dict:
    """
    Retrieves the base64 string of an image from the global store.
    
    Args:
        image_id (str): The ID of the image to retrieve.
        
    Returns:
        dict: A dictionary containing the image base64 and format, or None if not found.
    """
    if image_id in IMAGE_STORE:
        return {
            "base64_data": IMAGE_STORE[image_id]["base64_data"],
            "format": IMAGE_STORE[image_id]["format"]
        }
    return None
