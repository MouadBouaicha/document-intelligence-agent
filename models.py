from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from PIL import Image


@dataclass
class OCRRegion:
    """A single text region detected by OCR."""
    text: str
    bbox: list  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    confidence: float

    @property
    def bbox_xyxy(self) -> list:
        """Return bbox as [x1, y1, x2, y2] format."""
        x_coords = [p[0] for p in self.bbox]
        y_coords = [p[1] for p in self.bbox]
        return [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]


@dataclass
class LayoutRegion:
    """A layout region detected in the document."""
    region_id: int
    region_type: str
    bbox: list  # [x1, y1, x2, y2]
    confidence: float


@dataclass
class DocumentPage:
    """A single processed page of a document."""
    page_number: int
    image_path: Optional[str] = None
    image: Optional[Image.Image] = None
    ocr_regions: List[OCRRegion] = field(default_factory=list)
    layout_regions: List[LayoutRegion] = field(default_factory=list)
    ordered_text: List[Dict[str, Any]] = field(default_factory=list)
    region_images: Dict[int, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ProcessedDocument:
    """A fully processed document with all extracted data."""
    doc_id: str
    source_path: str
    pages: List[DocumentPage] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def source_name(self) -> str:
        return self.source_path.split("/")[-1].split("\\")[-1]

    def get_layout_summary(self) -> str:
        """Generate a layout summary for the agent system prompt."""
        lines = []
        for page in self.pages:
            lines.append(f"\n### Page {page.page_number}")
            for region in page.layout_regions:
                if region.confidence >= 0.5:
                    lines.append(
                        f"  - Region {region.region_id}: {region.region_type} "
                        f"(confidence: {region.confidence:.2f})"
                    )
        return "\n".join(lines)
