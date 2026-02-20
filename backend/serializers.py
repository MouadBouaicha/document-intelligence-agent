"""Convert internal models to JSON-safe dicts for API responses."""
from typing import Any, Dict, List

from models import DocumentPage, LayoutRegion, ProcessedDocument


def serialize_layout_region(region: LayoutRegion) -> Dict[str, Any]:
    return {
        "region_id": region.region_id,
        "region_type": region.region_type,
        "bbox": region.bbox,
        "confidence": round(region.confidence, 4),
    }


def serialize_page(page: DocumentPage) -> Dict[str, Any]:
    return {
        "page_number": page.page_number,
        "ocr_region_count": len(page.ocr_regions),
        "layout_region_count": len(page.layout_regions),
        "layout_regions": [serialize_layout_region(r) for r in page.layout_regions],
    }


def serialize_document(doc: ProcessedDocument) -> Dict[str, Any]:
    total_regions = sum(len(p.layout_regions) for p in doc.pages)
    total_text = sum(len(p.ocr_regions) for p in doc.pages)
    return {
        "doc_id": doc.doc_id,
        "filename": doc.source_name,
        "page_count": doc.page_count,
        "total_layout_regions": total_regions,
        "total_text_regions": total_text,
        "pages": [serialize_page(p) for p in doc.pages],
    }


def serialize_document_summary(doc: ProcessedDocument) -> Dict[str, Any]:
    """Lightweight summary for the document list sidebar."""
    total_regions = sum(len(p.layout_regions) for p in doc.pages)
    return {
        "doc_id": doc.doc_id,
        "filename": doc.source_name,
        "page_count": doc.page_count,
        "total_layout_regions": total_regions,
    }
