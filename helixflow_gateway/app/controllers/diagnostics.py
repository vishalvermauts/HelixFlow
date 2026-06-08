"""Active health, performance, and heartbeat endpoints."""
from fastapi import APIRouter
from ..contracts import StatusResponse

router = APIRouter()


@router.get("/health")
async def health():
    return StatusResponse(status="ok", details={})
