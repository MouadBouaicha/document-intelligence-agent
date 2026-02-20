"""Document upload, processing, and retrieval routes."""
import asyncio
import base64
import io
import json
import os
import traceback

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response, StreamingResponse

from backend.serializers import serialize_document, serialize_document_summary, serialize_layout_region
from backend.session import session_manager
from document_processor import process_document

UPLOADS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Pending uploads: doc_id -> {"tmp_path": str, "filename": str}
# Avoids passing Windows paths through URL query params.
_pending: dict = {}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Save uploaded file; compute doc_id from content hash; return metadata."""
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    content = await file.read()

    import hashlib
    doc_id = hashlib.sha256(content).hexdigest()[:16]

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    save_path = os.path.join(UPLOADS_DIR, f"{doc_id}{suffix}")
    if not os.path.exists(save_path):
        with open(save_path, "wb") as f:
            f.write(content)

    # Store path server-side so /process doesn't need it in the URL
    _pending[doc_id] = {"tmp_path": save_path, "filename": file.filename}

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "already_processed": session_manager.get_document(doc_id) is not None,
    }


@router.get("/{doc_id}/process")
async def process_document_sse(doc_id: str):
    """SSE stream: process document and emit progress events."""

    # Already loaded in session
    if session_manager.get_document(doc_id) is not None:
        async def already_done():
            yield f"event: progress\ndata: {json.dumps({'pct': 1.0, 'msg': 'Already processed'})}\n\n"
            yield f"event: done\ndata: {json.dumps({'doc_id': doc_id})}\n\n"
        return StreamingResponse(
            already_done(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    pending = _pending.get(doc_id)
    if pending is None:
        raise HTTPException(status_code=400, detail="Upload this document first via POST /api/documents/upload")

    tmp_path = pending["tmp_path"]
    filename = pending["filename"]

    async def event_stream():
        # ── Send an immediate ping so the browser knows the connection is live ──
        yield f"event: ping\ndata: {{}}\n\n"

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def progress_callback(current, total, msg):
            """Called from a worker thread — must be thread-safe."""
            pct = (current / total) if total > 0 else 0.0
            try:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"pct": min(pct, 1.0), "msg": msg},
                )
            except Exception:
                pass

        async def run_processing():
            try:
                doc = await loop.run_in_executor(
                    None,
                    lambda: process_document(tmp_path, progress_callback=progress_callback),
                )
                doc.source_path = filename
                session_manager.store_document(doc)
                _pending.pop(doc_id, None)
                await queue.put({"done": True, "doc_id": doc.doc_id})
            except Exception as exc:
                traceback.print_exc()
                await queue.put({"error": traceback.format_exc()})

        task = asyncio.create_task(run_processing())

        # Send a ping every 5 s so the browser doesn't close the idle connection
        # during long operations (EasyOCR, OpenAI API call, etc.)
        async def heartbeat():
            while True:
                await asyncio.sleep(5)
                await queue.put({"ping": True})

        hb_task = asyncio.create_task(heartbeat())

        try:
            while True:
                event = await queue.get()
                if "ping" in event:
                    yield f"event: ping\ndata: {{}}\n\n"
                elif "error" in event:
                    yield f"event: error\ndata: {json.dumps({'message': event['error']})}\n\n"
                    break
                elif "done" in event:
                    yield f"event: done\ndata: {json.dumps({'doc_id': event['doc_id']})}\n\n"
                    break
                else:
                    yield f"event: progress\ndata: {json.dumps(event)}\n\n"
        except Exception as exc:
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
        finally:
            hb_task.cancel()
            if not task.done():
                task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("")
async def list_documents():
    docs = session_manager.list_documents()
    return [serialize_document_summary(d) for d in docs]


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    doc = session_manager.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return serialize_document(doc)


@router.get("/{doc_id}/pages/{page}/image")
async def get_page_image(doc_id: str, page: int):
    doc = session_manager.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    page_obj = next((p for p in doc.pages if p.page_number == page), None)
    if page_obj is None:
        raise HTTPException(status_code=404, detail="Page not found")

    if page_obj.image is not None:
        buf = io.BytesIO()
        page_obj.image.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    elif page_obj.image_path and os.path.exists(page_obj.image_path):
        with open(page_obj.image_path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")
    else:
        raise HTTPException(status_code=404, detail="Page image not available")


@router.get("/{doc_id}/pages/{page}/layout")
async def get_page_layout(doc_id: str, page: int):
    doc = session_manager.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    page_obj = next((p for p in doc.pages if p.page_number == page), None)
    if page_obj is None:
        raise HTTPException(status_code=404, detail="Page not found")

    return {
        "page": page,
        "width": page_obj.image.width if page_obj.image else None,
        "height": page_obj.image.height if page_obj.image else None,
        "regions": [serialize_layout_region(r) for r in page_obj.layout_regions],
    }


@router.get("/{doc_id}/pages/{page}/regions/{region_id}/image")
async def get_region_image(doc_id: str, page: int, region_id: int):
    doc = session_manager.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    page_obj = next((p for p in doc.pages if p.page_number == page), None)
    if page_obj is None:
        raise HTTPException(status_code=404, detail="Page not found")

    region_data = page_obj.region_images.get(region_id)
    if region_data is None:
        raise HTTPException(status_code=404, detail="Region not found")

    img_bytes = base64.b64decode(region_data["base64"])
    return Response(content=img_bytes, media_type="image/png")


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    if session_manager.get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")

    session_manager.delete_document(doc_id)
    _pending.pop(doc_id, None)

    for fname in os.listdir(UPLOADS_DIR):
        if fname.startswith(doc_id):
            try:
                os.unlink(os.path.join(UPLOADS_DIR, fname))
            except OSError:
                pass

    return {"status": "deleted", "doc_id": doc_id}
