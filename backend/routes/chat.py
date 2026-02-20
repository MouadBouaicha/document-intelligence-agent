"""Chat endpoint with SSE streaming and tool call visibility."""
import json
import asyncio
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import create_agent, stream_agent
from backend.session import session_manager

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    doc_id: str
    message: str
    session_id: str = ""


@router.post("")
async def chat(request: ChatRequest):
    """Stream agent response for a user message.

    SSE events:
      - tool_call:   {"name": str, "args": dict}
      - tool_result: {"name": str, "result": str}
      - answer:      {"content": str}
      - error:       {"message": str}
    """
    doc = session_manager.get_document(request.doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Resolve or create session
    session_id = request.session_id or str(uuid.uuid4())
    agent = session_manager.get_agent(session_id)

    # Create new agent if session doesn't have one or is for a different doc
    current_doc_id = session_manager.get_session_doc_id(session_id)
    if agent is None or current_doc_id != request.doc_id:
        agent = create_agent(doc)
        session_manager.store_agent(session_id, agent, request.doc_id)

    async def event_stream():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def run_stream():
            try:
                for event in stream_agent(agent, request.message, session_id=session_id):
                    asyncio.run_coroutine_threadsafe(queue.put(event), loop)
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(
                    queue.put({"type": "error", "data": {"message": str(exc)}}),
                    loop,
                )
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        # Run blocking stream in thread pool
        loop.run_in_executor(None, run_stream)

        while True:
            event = await queue.get()
            if event is None:
                break
            sse_event = event["type"]
            sse_data = json.dumps(event["data"])
            yield f"event: {sse_event}\ndata: {sse_data}\n\n"

    # Include session_id in a startup event so the client can save it
    async def full_stream():
        yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"
        async for chunk in event_stream():
            yield chunk

    return StreamingResponse(
        full_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/history")
async def clear_history(session_id: str):
    """Clear chat history for a session."""
    session_manager.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
