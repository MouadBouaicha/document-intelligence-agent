import base64
from io import BytesIO
from pathlib import Path
from typing import List

from PIL import Image


def crop_region(image: Image.Image, bbox: list, padding: int = 10) -> Image.Image:
    """Crop a region from image with optional padding."""
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(image.width, x2 + padding)
    y2 = min(image.height, y2 + padding)
    return image.crop((x1, y1, x2, y2))


def image_to_base64(img: Image.Image) -> str:
    """Convert PIL Image to base64 string."""
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def pdf_to_images(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """Convert PDF pages to PIL images using PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    images = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images


def load_document_images(file_path: str) -> List[Image.Image]:
    """Load images from a file path. Handles PDFs and image files."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return pdf_to_images(file_path)
    elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
        return [Image.open(file_path).convert("RGB")]
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file for caching."""
    import hashlib

    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]
