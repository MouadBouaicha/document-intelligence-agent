import os
import tempfile
from pathlib import Path
from typing import List

from PIL import Image

from models import ProcessedDocument, DocumentPage, OCRRegion, LayoutRegion
from utils import compute_file_hash, image_to_base64, crop_region

_cache = {}


# ── Rect-merging helper ──────────────────────────────────────────────────────

def _merge_rects(rects, gap: int = 8):
    """
    Merge a list of fitz.Rect objects that overlap or are within `gap` pts of
    each other.  Uses union-find so nearby elements that form a chain are all
    combined into one bounding box.
    """
    import fitz

    n = len(rects)
    if n == 0:
        return []

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        pa, pb = find(a), find(b)
        if pa != pb:
            parent[pa] = pb

    expanded = [fitz.Rect(r.x0 - gap, r.y0 - gap, r.x1 + gap, r.y1 + gap)
                for r in rects]

    for i in range(n):
        for j in range(i + 1, n):
            if expanded[i].intersects(expanded[j]):
                union(i, j)

    groups: dict = {}
    for i in range(n):
        root = find(i)
        groups[root] = groups[root] | rects[i] if root in groups else fitz.Rect(rects[i])

    return list(groups.values())


# ── PDF extraction via PyMuPDF ───────────────────────────────────────────────

def _process_pdf(file_path: str, progress_callback=None) -> List[DocumentPage]:
    import fitz

    pdf      = fitz.open(file_path)
    total    = len(pdf)
    pages    = []
    temp_dir = tempfile.mkdtemp(prefix="doc_agent_")

    for i, fitz_page in enumerate(pdf):
        page_num = i + 1
        if progress_callback:
            progress_callback(i, total, f"Processing page {page_num}/{total}…")

        # Render at 120 DPI
        mat = fitz.Matrix(120 / 72, 120 / 72)
        pix = fitz_page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_path = os.path.join(temp_dir, f"page_{page_num}.png")
        img.save(img_path, format="PNG")

        sx = img.width  / fitz_page.rect.width   # scale PDF-pts → pixels
        sy = img.height / fitz_page.rect.height

        layout_regions: List[LayoutRegion] = []
        ocr_regions:    List[OCRRegion]    = []
        ordered_text:   list               = []
        region_images:  dict               = {}
        rid     = 0   # global region id counter
        text_pos = 0  # reading-order position for ordered_text

        table_rects = []   # fitz.Rect list – used to exclude overlapping elements

        # ── 1. Tables ─────────────────────────────────────────────────────────
        try:
            detected = fitz_page.find_tables()
            for table in detected.tables:
                r = fitz.Rect(table.bbox)
                table_rects.append(r)

                ix0, iy0 = int(r.x0 * sx), int(r.y0 * sy)
                ix1, iy1 = int(r.x1 * sx), int(r.y1 * sy)

                layout_regions.append(LayoutRegion(
                    region_id=rid, region_type="table",
                    bbox=[ix0, iy0, ix1, iy1], confidence=1.0,
                ))
                cropped = crop_region(img, [ix0, iy0, ix1, iy1])
                region_images[rid] = {
                    "image": cropped, "base64": image_to_base64(cropped),
                    "type": "table", "bbox": [ix0, iy0, ix1, iy1],
                }

                # Put table text (pipe-separated rows) into ordered_text
                try:
                    rows = table.extract()
                    table_text = "\n".join(
                        " | ".join(str(c or "").strip() for c in row)
                        for row in rows if any(c for c in row)
                    )
                except Exception:
                    table_text = ""

                if table_text.strip():
                    ordered_text.append({
                        "position": text_pos,
                        "text": f"[TABLE region_id={rid}]\n{table_text}",
                        "confidence": 1.0,
                        "bbox": [ix0, iy0, ix1, iy1],
                    })
                    text_pos += 1

                rid += 1
        except Exception as e:
            print(f"[processor] table detection skipped on page {page_num}: {e}", flush=True)

        # ── 2. Figures (raster images + vector drawings, merged) ─────────────
        raw_figure_rects = []

        # 2a. Raster images embedded in the PDF
        try:
            for info in fitz_page.get_image_info():
                r = fitz.Rect(info["bbox"])
                if r.width > 20 and r.height > 20:
                    raw_figure_rects.append(r)
        except Exception:
            pass

        # 2b. Vector drawings (charts, plots, diagrams are usually vectors)
        try:
            for drawing in fitz_page.get_drawings():
                r = fitz.Rect(drawing["rect"])
                # Skip hairlines (borders/underlines) but keep substantial shapes
                if r.width > 20 and r.height > 20:
                    raw_figure_rects.append(r)
        except Exception:
            pass

        # Remove any rect that is inside a table
        raw_figure_rects = [
            r for r in raw_figure_rects
            if not any(r.intersects(tr) for tr in table_rects)
        ]

        # Merge nearby/overlapping rects into single figure regions
        merged_figure_rects = _merge_rects(raw_figure_rects, gap=8)

        # Only keep merged regions large enough to be a real figure
        for r in merged_figure_rects:
            if r.width < 60 or r.height < 60:
                continue
            # Skip if fully overlapping a table
            if any(r.intersects(tr) for tr in table_rects):
                continue

            ix0, iy0 = int(r.x0 * sx), int(r.y0 * sy)
            ix1, iy1 = int(r.x1 * sx), int(r.y1 * sy)

            # Clamp to image bounds
            ix0, iy0 = max(0, ix0), max(0, iy0)
            ix1, iy1 = min(img.width, ix1), min(img.height, iy1)
            if ix1 <= ix0 or iy1 <= iy0:
                continue

            layout_regions.append(LayoutRegion(
                region_id=rid, region_type="figure",
                bbox=[ix0, iy0, ix1, iy1], confidence=1.0,
            ))
            cropped = crop_region(img, [ix0, iy0, ix1, iy1])
            region_images[rid] = {
                "image": cropped, "base64": image_to_base64(cropped),
                "type": "figure", "bbox": [ix0, iy0, ix1, iy1],
            }
            rid += 1

        # Collect all non-text rects to exclude from text extraction
        figure_rects = [
            fitz.Rect(lr.bbox[0] / sx, lr.bbox[1] / sy,
                      lr.bbox[2] / sx, lr.bbox[3] / sy)
            for lr in layout_regions if lr.region_type == "figure"
        ]
        exclude_rects = table_rects + figure_rects

        # ── 3. Text blocks (skip anything inside tables or figures) ───────────
        for b in fitz_page.get_text("blocks"):
            x0, y0, x1, y1, text, _, btype = b
            if btype != 0 or not text.strip():
                continue

            block_rect = fitz.Rect(x0, y0, x1, y1)
            if any(block_rect.intersects(er) for er in exclude_rects):
                continue

            ix0, iy0 = int(x0 * sx), int(y0 * sy)
            ix1, iy1 = int(x1 * sx), int(y1 * sy)

            ocr_regions.append(OCRRegion(
                text=text.strip(),
                bbox=[[ix0, iy0], [ix1, iy0], [ix1, iy1], [ix0, iy1]],
                confidence=1.0,
            ))
            layout_regions.append(LayoutRegion(
                region_id=rid, region_type="text",
                bbox=[ix0, iy0, ix1, iy1], confidence=1.0,
            ))
            cropped = crop_region(img, [ix0, iy0, ix1, iy1])
            region_images[rid] = {
                "image": cropped, "base64": image_to_base64(cropped),
                "type": "text", "bbox": [ix0, iy0, ix1, iy1],
            }
            ordered_text.append({
                "position": text_pos,
                "text": text.strip(),
                "confidence": 1.0,
                "bbox": [ix0, iy0, ix1, iy1],
            })
            text_pos += 1
            rid += 1

        pages.append(DocumentPage(
            page_number=page_num,
            image_path=img_path,
            image=img,
            ocr_regions=ocr_regions,
            layout_regions=layout_regions,
            ordered_text=ordered_text,
            region_images=region_images,
        ))

    pdf.close()
    return pages


# ── Image files via EasyOCR ──────────────────────────────────────────────────

def _process_image(file_path: str, progress_callback=None) -> List[DocumentPage]:
    from ocr import run_ocr, get_reading_order, get_ordered_text
    from layout import detect_layout, crop_all_regions

    if progress_callback:
        progress_callback(0, 1, "Running OCR…")

    image    = Image.open(file_path).convert("RGB")
    temp_dir = tempfile.mkdtemp(prefix="doc_agent_")
    img_path = os.path.join(temp_dir, "page_1.png")
    image.save(img_path, format="PNG")

    ocr_regions  = run_ocr(img_path)
    ordered_text = []
    if ocr_regions:
        reading_order = get_reading_order(ocr_regions)
        ordered_text  = get_ordered_text(ocr_regions, reading_order)

    layout_regions = detect_layout(img_path)
    region_images  = crop_all_regions(image, layout_regions)

    return [DocumentPage(
        page_number=1, image_path=img_path, image=image,
        ocr_regions=ocr_regions, layout_regions=layout_regions,
        ordered_text=ordered_text, region_images=region_images,
    )]


# ── Entry point ──────────────────────────────────────────────────────────────

def process_document(file_path: str, progress_callback=None) -> ProcessedDocument:
    file_hash = compute_file_hash(file_path)
    if file_hash in _cache:
        return _cache[file_hash]

    suffix = Path(file_path).suffix.lower()
    pages  = (_process_pdf(file_path, progress_callback) if suffix == ".pdf"
              else _process_image(file_path, progress_callback))

    doc = ProcessedDocument(doc_id=file_hash, source_path=file_path, pages=pages)
    _cache[file_hash] = doc
    return doc
