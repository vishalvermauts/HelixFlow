from fastapi import APIRouter, Request
from helixflow_gateway.contracts import StatusResponse

router = APIRouter()


@router.get("/health", response_model=StatusResponse)
async def check_health(request: Request):
    cache_layer = request.app.state.cache_layer
    try:
        await cache_layer.ping()
        cache_status = "connected"
    except Exception:
        cache_status = "unreachable"

    return StatusResponse(
        status="online",
        engine="HelixFlow-Gateway Core System",
        cache=cache_status,
    )
