import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.routes import documents, chat, chunks

app = FastAPI(
    title="Document Intelligence Agent",
    description="FastAPI backend for the Document Intelligence Agent",
    version="2.0.0",
)

# --- Routers ---
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(chunks.router)

# --- Static files ---
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/", include_in_schema=False)
async def serve_spa():
    """Serve the single-page application shell."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
