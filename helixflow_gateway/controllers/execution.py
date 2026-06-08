import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from helixflow_gateway.contracts import InferenceRequest
from helixflow_gateway.dispatch_matrix import calculate_routing_score
from helixflow_gateway.infrastructure.fabric_connectors import stream_forwarder

router = APIRouter()


async def token_transit_pipeline(stream_gen, cache, telemetry_packet):
    start_epoch = telemetry_packet["initiated_epoch"]
    ttft_captured = False

    async for token_chunk in stream_gen:
        if not ttft_captured:
            telemetry_packet["time_to_first_token_ms"] = int((time.time() - start_epoch) * 1000)
            ttft_captured = True
        yield token_chunk

    telemetry_packet["total_duration_ms"] = int((time.time() - start_epoch) * 1000)
    try:
        await cache.xadd("gateway:telemetry", telemetry_packet, id="*")
    except Exception:
        pass


@router.post("/stream")
async def process_inference_stream(payload: InferenceRequest, request: Request):
    start_epoch = time.time()

    target_model = payload.model
    if target_model == "auto":
        target_model = calculate_routing_score(payload.messages)

    outbound_payload = payload.model_dump()
    outbound_payload["model"] = target_model

    stream_gen = stream_forwarder(target_model, outbound_payload)

    telemetry_packet = {
        "tenant_id": getattr(request.state, "tenant_id", "anonymous"),
        "token_hash": getattr(request.state, "token_hash", ""),
        "requested_model": payload.model,
        "assigned_model": target_model,
        "initiated_epoch": start_epoch,
    }

    return StreamingResponse(
        token_transit_pipeline(stream_gen, request.app.state.cache_layer, telemetry_packet),
        media_type="text/event-stream",
    )
