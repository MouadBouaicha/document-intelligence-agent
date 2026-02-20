from typing import List, Dict, Any

from models import OCRRegion

_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _reader


def run_ocr(image_path: str) -> List[OCRRegion]:
    """Run EasyOCR on an image and return structured OCR regions."""
    reader = _get_reader()
    results = reader.readtext(image_path)

    regions = []
    for (bbox, text, conf) in results:
        if not text.strip():
            continue
        # EasyOCR bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
        regions.append(OCRRegion(
            text=text,
            bbox=[[int(p[0]), int(p[1])] for p in bbox],
            confidence=float(conf),
        ))
    return regions


def get_reading_order(ocr_regions: List[OCRRegion]) -> List[int]:
    """Return reading order indices sorted top-to-bottom, left-to-right."""
    indexed = list(range(len(ocr_regions)))
    indexed.sort(key=lambda i: (ocr_regions[i].bbox_xyxy[1], ocr_regions[i].bbox_xyxy[0]))
    order = [0] * len(ocr_regions)
    for rank, idx in enumerate(indexed):
        order[idx] = rank
    return order


def get_ordered_text(
    ocr_regions: List[OCRRegion], reading_order: List[int]
) -> List[Dict[str, Any]]:
    """Return OCR regions sorted by reading order."""
    indexed = [(reading_order[i], i, ocr_regions[i]) for i in range(len(ocr_regions))]
    indexed.sort(key=lambda x: x[0])
    return [
        {
            "position": pos,
            "text": r.text,
            "confidence": r.confidence,
            "bbox": r.bbox_xyxy,
        }
        for pos, _, r in indexed
    ]
