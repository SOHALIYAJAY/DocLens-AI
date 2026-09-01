# services/image_service.py
import fitz  # PyMuPDF
import base64
import uuid
import io
import hashlib
from PIL import Image, ImageStat

# Global in-memory store for images. 
# Maps image_id (str) to a dict containing {"base64_data": str, "format": str, "bytes": bytes}
IMAGE_STORE = {}

def is_valid_content_image(image_bytes: bytes, width: int, height: int) -> bool:
    """
    Filters out raw 1px solid black/white boxes, 1x1 bullet dots, and blank masks,
    while accurately keeping all real images, charts, diagrams, logos, and figures.
    """
    # 1. Minimum dimensions (filters 1x1 pixels, thin 1px lines, tiny bullet dots)
    if width < 25 or height < 25 or (width * height) < 600:
        return False
        
    # 2. Extreme aspect ratio filter (e.g. 1px line separators spanning whole page)
    aspect_ratio = max(width, height) / max(min(width, height), 1)
    if aspect_ratio > 15.0:
        return False
        
    try:
        # 3. Analyze pixels with PIL
        img = Image.open(io.BytesIO(image_bytes))
        rgb_img = img.convert("RGB")
        
        # Check extrema (min, max per RGB channel)
        extrema = rgb_img.getextrema()
        # If R_min == R_max and G_min == G_max and B_min == B_max, it's a solid 100% single-color box
        if all(c[0] == c[1] for c in extrema):
            return False
            
        # Check standard deviation of color channels
        stat = ImageStat.Stat(rgb_img)
        # Low variance across channels (< 0.2) indicates a completely solid blank mask/overlay
        if max(stat.stddev) < 0.2:
            return False

        return True
    except Exception as e:
        print(f"Image validation warning: {e}")
        # Default to True on warning so real images are never lost
        return True


def extract_and_store_images(file_bytes: bytes) -> list[dict]:
    """
    Extracts high-quality content images AND vector diagrams/figures from a PDF file using PyMuPDF.
    Clears IMAGE_STORE on every new document upload to avoid showing old PDF images.
    
    Args:
        file_bytes (bytes): The raw bytes of the uploaded PDF file.
        
    Returns:
        list[dict]: A list of dictionaries containing image metadata (image_id, page, format).
    """
    try:
        # Clear previous session's images so old PDF images aren't returned!
        IMAGE_STORE.clear()
        
        extracted_images = []
        
        # Open PDF from bytes
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # 1. Extract embedded raster images (JPEG, PNG, etc.)
            images = page.get_images(full=True)
            page_seen_hashes = set()
            
            for img_index, img in enumerate(images):
                xref = img[0]
                
                # Extract image bytes and dimensions
                try:
                    base_image = doc.extract_image(xref)
                except Exception:
                    continue

                if not base_image or "image" not in base_image:
                    continue

                image_bytes = base_image["image"]
                image_ext = base_image.get("ext", "png")
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                
                # Skip duplicate images on the exact same page
                img_hash = hashlib.md5(image_bytes).hexdigest()
                if img_hash in page_seen_hashes:
                    continue
                
                # Filter out non-content images (1px line separators, blank masks)
                if not is_valid_content_image(image_bytes, width, height):
                    continue
                    
                page_seen_hashes.add(img_hash)
                
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
                    "image_index": len(page_seen_hashes),
                    "format": image_ext
                })

            # 2. Extract non-image vector diagrams, flowcharts, & drawn figures
            # If a page contains vector drawings (shapes, lines, curves, block diagrams) but no embedded images:
            try:
                drawings = page.get_drawings()
                if len(images) == 0 and len(drawings) >= 3:
                    pix = page.get_pixmap(dpi=150)
                    diagram_bytes = pix.tobytes("png")
                    width, height = pix.width, pix.height
                    
                    diagram_hash = hashlib.md5(diagram_bytes).hexdigest()
                    if diagram_hash not in page_seen_hashes and is_valid_content_image(diagram_bytes, width, height):
                        page_seen_hashes.add(diagram_hash)
                        diagram_base64 = base64.b64encode(diagram_bytes).decode("utf-8")
                        image_id = str(uuid.uuid4())
                        
                        IMAGE_STORE[image_id] = {
                            "base64_data": diagram_base64,
                            "format": "png",
                            "bytes": diagram_bytes
                        }
                        
                        extracted_images.append({
                            "image_id": image_id,
                            "page": page_num + 1,
                            "image_index": len(page_seen_hashes),
                            "format": "png"
                        })
            except Exception as ve:
                print(f"Vector diagram extraction warning on page {page_num + 1}: {ve}")
                
        doc.close()
        return extracted_images
        
    except Exception as e:
        print(f"Failed to extract images from PDF: {str(e)}")
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

