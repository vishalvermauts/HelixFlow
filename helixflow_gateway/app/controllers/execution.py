"""Core non-blocking token stream proxy data highway (stub)."""
from fastapi import APIRouter, Response
from ..contracts import StreamRequest

router = APIRouter()


@router.post("/stream")
async def stream_proxy(req: StreamRequest):
    """Placeholder endpoint for streaming proxy behavior."""
    # In a real implementation this would stream tokens via Server-Sent Events
    return {"status": "accepted", "model": req.model}
