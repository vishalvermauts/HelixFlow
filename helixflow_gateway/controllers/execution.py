import time
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from helixflow_gateway.contracts import InferenceRequest
from helixflow_gateway.dispatch_matrix import calculate_routing_score_async
from helixflow_gateway.infrastructure.fabric_connectors import stream_forwarder, non_stream_forwarder

router = APIRouter()


async def token_transit_pipeline(stream_gen, cache, telemetry_packet):
    start_epoch = telemetry_packet["initiated_epoch"]
    ttft_captured = False
    completion_chars = 0

    async for token_chunk in stream_gen:
        if not ttft_captured:
            telemetry_packet["time_to_first_token_ms"] = int((time.time() - start_epoch) * 1000)
            ttft_captured = True
        
        # Increment completion characters by inspecting raw SSE stream chunk content
        chunk_str = token_chunk.decode("utf-8", errors="ignore")
        if '"content":"' in chunk_str:
            parts = chunk_str.split('"content":"')
            for part in parts[1:]:
                end_idx = part.find('"')
                if end_idx != -1:
                    completion_chars += len(part[:end_idx])
                    
        yield token_chunk

    telemetry_packet["total_duration_ms"] = int((time.time() - start_epoch) * 1000)
    
    # Calculate exact completion tokens (approx. 4 characters per token)
    telemetry_packet["completion_tokens"] = max(1, completion_chars // 4)
    telemetry_packet["tokens"] = telemetry_packet["prompt_tokens"] + telemetry_packet["completion_tokens"]
    
    try:
        await cache.xadd("gateway:telemetry", telemetry_packet, id="*")
    except Exception:
        pass


async def resolve_target_model(requested_model: str, messages, cache) -> str:
    if requested_model in ["auto", "deepseek-chat", "openai/helix-auto-router", "helix-auto-router"]:
        routing_mode = "auto"
        try:
            config_json = await cache.get("gateway:config")
            if config_json:
                config = json.loads(config_json)
                routing_mode = config.get("default_routing", {}).get("mode", "auto")
        except Exception:
            pass

        if routing_mode == "bypass-speed":
            return "fabric-speed-edge"
        elif routing_mode == "bypass-dense":
            return "fabric-dense-reasoning"
        else:
            # Dynamic routing — checks which providers have keys in Redis
            return await calculate_routing_score_async(messages, cache)
    return requested_model


def extract_telemetry_fields(request: Request, payload: InferenceRequest, target_model: str, start_epoch: float) -> dict:
    # Extract metadata headers
    project = request.headers.get("x-project") or request.headers.get("X-Project") or "default"
    tags = request.headers.get("x-tag") or request.headers.get("x-tags") or request.headers.get("X-Tag") or request.headers.get("X-Tags") or "env:production"
    
    # Extract masked token
    auth_header = request.headers.get("Authorization")
    masked_token = "unknown"
    if auth_header and auth_header.startswith("Bearer "):
        raw_token = auth_header.split(" ")[1]
        masked_token = raw_token[:12] + "..." if len(raw_token) > 12 else raw_token

    # Pre-calculate prompt tokens (approx. 4 characters per token)
    prompt_chars = sum(len(m.content) for m in payload.messages)
    prompt_tokens = max(1, prompt_chars // 4)

    # Resolve human-readable provider name from fabric key
    provider_map = {
        "fabric-speed-edge":        "DeepSeek",
        "fabric-dense-reasoning":   "Google Gemini",
        "fabric-anthropic-claude":  "Anthropic Claude",
        "fabric-openai-gpt4o":      "OpenAI GPT-4o",
        "fabric-openai-gpt4o-mini": "OpenAI GPT-4o Mini",
    }
    provider = provider_map.get(target_model, target_model)

    return {
        "tenant_id": getattr(request.state, "tenant_id", "anonymous"),
        "token_hash": getattr(request.state, "token_hash", ""),
        "requested_model": payload.model,
        "assigned_model": target_model,
        "provider": provider,
        "initiated_epoch": start_epoch,
        "project": project,
        "tags": tags,
        "masked_token": masked_token,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": 0,
        "tokens": prompt_tokens,
    }


@router.post("/stream")
async def process_inference_stream(payload: InferenceRequest, request: Request):
    start_epoch = time.time()
    cache_layer = request.app.state.cache_layer

    target_model = await resolve_target_model(payload.model, payload.messages, cache_layer)

    outbound_payload = payload.model_dump()
    outbound_payload["model"] = target_model

    auth_header = request.headers.get("Authorization")
    stream_gen = stream_forwarder(
        target_model, outbound_payload, client_auth_header=auth_header, cache_client=cache_layer
    )

    telemetry_packet = extract_telemetry_fields(request, payload, target_model, start_epoch)

    return StreamingResponse(
        token_transit_pipeline(stream_gen, cache_layer, telemetry_packet),
        media_type="text/event-stream",
    )


@router.post("/chat/completions")
@router.post("/v1/chat/completions")
async def chat_completions(payload: InferenceRequest, request: Request):
    start_epoch = time.time()
    cache_layer = request.app.state.cache_layer

    target_model = await resolve_target_model(payload.model, payload.messages, cache_layer)

    outbound_payload = payload.model_dump()
    outbound_payload["model"] = target_model

    telemetry_packet = extract_telemetry_fields(request, payload, target_model, start_epoch)

    auth_header = request.headers.get("Authorization")
    if payload.stream:
        stream_gen = stream_forwarder(
            target_model, outbound_payload, client_auth_header=auth_header, cache_client=cache_layer
        )
        return StreamingResponse(
            token_transit_pipeline(stream_gen, cache_layer, telemetry_packet),
            media_type="text/event-stream",
        )
    else:
        try:
            res_json = await non_stream_forwarder(
                target_model, outbound_payload, client_auth_header=auth_header, cache_client=cache_layer
            )
            duration_ms = int((time.time() - start_epoch) * 1000)
            telemetry_packet["time_to_first_token_ms"] = duration_ms
            telemetry_packet["total_duration_ms"] = duration_ms
            
            # Extract actual tokens from downstream response
            usage = res_json.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", telemetry_packet["prompt_tokens"])
            completion_tokens = usage.get("completion_tokens", 0)
            if completion_tokens == 0:
                choices = res_json.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    completion_tokens = len(content) // 4
            
            telemetry_packet["prompt_tokens"] = prompt_tokens
            telemetry_packet["completion_tokens"] = completion_tokens
            telemetry_packet["tokens"] = prompt_tokens + completion_tokens
            
            try:
                await cache_layer.xadd("gateway:telemetry", telemetry_packet, id="*")
            except Exception:
                pass
            return JSONResponse(content=res_json)
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Downstream request failed: {repr(e)}"})

