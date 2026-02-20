from typing import List, Dict, Any

from PIL import Image

from models import LayoutRegion
from utils import crop_region, image_to_base64


def detect_layout(image_path: str) -> List[LayoutRegion]:
    """Detect layout regions using EasyOCR bounding boxes.

    Each OCR text box becomes a 'text' layout region.
    Large non-text areas are heuristically marked as 'figure'.
    """
    from ocr import run_ocr
    ocr_regions = run_ocr(image_path)

    regions = []
    for i, ocr_region in enumerate(ocr_regions):
        x1, y1, x2, y2 = ocr_region.bbox_xyxy
        regions.append(LayoutRegion(
            region_id=i,
            region_type="text",
            bbox=[x1, y1, x2, y2],
            confidence=ocr_region.confidence,
        ))

    return regions


def crop_all_regions(
    image: Image.Image, layout_regions: List[LayoutRegion]
) -> Dict[int, Dict[str, Any]]:
    """Crop all layout regions from an image and return as dict."""
    region_images = {}
    for region in layout_regions:
        cropped = crop_region(image, region.bbox)
        region_images[region.region_id] = {
            "image": cropped,
            "base64": image_to_base64(cropped),
            "type": region.region_type,
            "bbox": region.bbox,
        }
    return region_images
