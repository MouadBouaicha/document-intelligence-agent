"""Chunk explorer API — returns the ordered text regions from the processed document."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.session import session_manager

router = APIRouter(prefix="/api/documents", tags=["chunks"])


@router.get("/{doc_id}/chunks")
async def get_chunks(
    doc_id: str,
    page: Optional[int] = Query(None, description="Filter by page number"),
    search: Optional[str] = Query(None, description="Substring text filter"),
    limit: int = Query(500, ge=1, le=2000),
):
    doc = session_manager.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = []
    for pg in doc.pages:
        if page is not None and pg.page_number != page:
            continue
        for item in pg.ordered_text:
            text = item.get("text", "")
            if search and search.lower() not in text.lower():
                continue
            chunks.append({
                "id": f"{doc_id}_p{pg.page_number}_r{item['position']}",
                "text": text,
                "page_number": pg.page_number,
                "chunk_index": item["position"],
            })

    chunks.sort(key=lambda c: (c["page_number"], c["chunk_index"]))

    return {
        "doc_id": doc_id,
        "total": len(chunks),
        "chunks": chunks[:limit],
    }
