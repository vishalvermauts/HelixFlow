import asyncio
import json
import time
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from helixflow_gateway.infrastructure.fabric_connectors import non_stream_forwarder, stream_forwarder

router = APIRouter(prefix="/api/dashboard")

class SimulationRequest(BaseModel):
    model_a: str
    model_b: str
    user_message: str
    system_prompt: Optional[str] = ""
    stream: bool = False

# --- Endpoints ---

@router.get("/stats")
async def get_stats(request: Request):
    """Retrieves aggregated usage statistics from telemetry."""
    cache = request.app.state.cache_layer
    try:
        stream_data = await cache.xrevrange("gateway:telemetry", max="+", min="-", count=100)
    except Exception:
        stream_data = []

    if not stream_data:
        # Return clean empty stats if no traffic has occurred
        return JSONResponse(content={
            "total_spend": 0.00,
            "avg_latency": 0,
            "by_provider": [],
            "by_vendor": [],
            "by_model": [],
            "by_project": [],
            "by_tag": [],
            "by_customer": [],
            "by_api_key": [],
            "daily_trend": []
        })

    # Aggregate actual stream records
    total_spend = 0.0
    total_latency = 0
    count_latency = 0

    provider_counts = {}
    model_counts = {}
    tenant_counts = {}
    project_counts = {}
    tag_counts = {}
    api_key_counts = {}

    # Cost calculators based on models (standard input/output rates per token)
    def calculate_exact_cost(model, prompt_tokens, completion_tokens):
        if "deepseek" in model or "speed" in model:
            input_rate = 0.14 / 1_000_000   # $0.14 per 1M tokens
            output_rate = 0.28 / 1_000_000  # $0.28 per 1M tokens
        elif "gemini" in model or "dense" in model:
            input_rate = 1.25 / 1_000_000   # $1.25 per 1M tokens
            output_rate = 5.00 / 1_000_000  # $5.00 per 1M tokens
        elif "claude" in model or "anthropic" in model:
            input_rate = 3.00 / 1_000_000   # $3.00 per 1M tokens (Sonnet 3.5)
            output_rate = 15.00 / 1_000_000 # $15.00 per 1M tokens (Sonnet 3.5)
        else:
            input_rate = 0.50 / 1_000_000
            output_rate = 1.50 / 1_000_000
        return (prompt_tokens * input_rate) + (completion_tokens * output_rate)

    # For 7 days trend
    import datetime
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    daily_spend = {day.strftime("%b %d"): 0.0 for day in days}
    daily_tokens = {day.strftime("%b %d"): 0 for day in days}

    for idx, fields in stream_data:
        model = fields.get("assigned_model", "unknown")
        tenant = fields.get("tenant_id", "anonymous")
        project = fields.get("project", "default")
        tags = fields.get("tags", "env:production")
        masked_token = fields.get("masked_token", "unknown")
        
        dur = float(fields.get("total_duration_ms", 0))
        if dur > 0:
            total_latency += dur
            count_latency += 1

        prompt_tokens = int(fields.get("prompt_tokens", 100))
        completion_tokens = int(fields.get("completion_tokens", 0))
        if completion_tokens == 0:
            # Fallback estimation for legacy entries
            total_t = int(fields.get("tokens", dur // 2))
            completion_tokens = max(1, total_t - prompt_tokens)

        cost = calculate_exact_cost(model, prompt_tokens, completion_tokens)
        total_spend += cost

        # Accumulate metrics
        model_counts[model] = model_counts.get(model, 0.0) + cost
        tenant_counts[tenant] = tenant_counts.get(tenant, 0.0) + cost
        project_counts[project] = project_counts.get(project, 0.0) + cost
        api_key_counts[masked_token] = api_key_counts.get(masked_token, 0.0) + cost
        
        # Accumulate tags (split by comma)
        for t in tags.split(","):
            t = t.strip()
            if t:
                tag_counts[t] = tag_counts.get(t, 0.0) + cost

        # Provider mapping
        provider = "Anthropic" if ("claude" in model or "anthropic" in model) else "Google Gemini" if ("gemini" in model or "dense" in model) else "DeepSeek" if ("deepseek" in model or "speed" in model) else "Other"
        provider_counts[provider] = provider_counts.get(provider, 0.0) + cost

        # Daily trend
        epoch = float(fields.get("initiated_epoch", time.time()))
        date_str = datetime.date.fromtimestamp(epoch).strftime("%b %d")
        if date_str in daily_spend:
            daily_spend[date_str] += cost
            daily_tokens[date_str] += int(fields.get("tokens", dur // 2))

    avg_latency = int(total_latency / count_latency) if count_latency > 0 else 0

    # Convert helpers
    def to_sorted_percentage_list(counts_dict):
        items = []
        for label, val in counts_dict.items():
            items.append({
                "label": label,
                "value": round(val, 4),
                "percentage": round((val / total_spend) * 100, 1) if total_spend > 0 else 0
            })
        items.sort(key=lambda x: x["value"], reverse=True)
        return items

    by_provider = to_sorted_percentage_list(provider_counts)
    by_model = to_sorted_percentage_list(model_counts)
    by_project = to_sorted_percentage_list(project_counts)
    by_tag = to_sorted_percentage_list(tag_counts)
    by_customer = to_sorted_percentage_list(tenant_counts)
    by_api_key = to_sorted_percentage_list(api_key_counts)

    daily_trend = []
    for day in days:
        day_str = day.strftime("%b %d")
        daily_trend.append({
            "date": day_str,
            "spend": round(daily_spend[day_str], 4),
            "tokens": daily_tokens[day_str]
        })

    return {
        "total_spend": round(total_spend, 4),
        "avg_latency": avg_latency,
        "by_provider": by_provider,
        "by_vendor": [{"label": "Helix Router", "value": round(total_spend, 4), "percentage": 100.0}],
        "by_model": by_model,
        "by_project": by_project,
        "by_tag": by_tag,
        "by_customer": by_customer,
        "by_api_key": by_api_key,
        "daily_trend": daily_trend
    }


@router.get("/logs")
async def get_logs(request: Request):
    """Retrieves execution logs from Redis stream."""
    cache = request.app.state.cache_layer
    try:
        stream_data = await cache.xrevrange("gateway:telemetry", max="+", min="-", count=100)
    except Exception:
        stream_data = []

    if not stream_data:
        return []

    formatted_logs = []
    for item_id, fields in stream_data:
        epoch = float(fields.get("initiated_epoch", time.time()))
        
        req_model = fields.get("requested_model", "auto")
        assigned_model = fields.get("assigned_model", "fabric-speed-edge")
        provider = fields.get("provider", "")

        # Friendly routing description
        if req_model in ["auto", "openai/helix-auto-router", "helix-auto-router", "deepseek-chat"]:
            policy_str = f"Auto-Route → {provider}" if provider else f"Auto-Route → {assigned_model}"
        else:
            policy_str = f"Static Override ({req_model})"
        
        latency = int(fields.get("total_duration_ms", 0))
        ttft = int(fields.get("time_to_first_token_ms", 0))
        project = fields.get("project", "default")
        
        formatted_logs.append({
            "timestamp": epoch,
            "policy": policy_str,
            "provider": provider or assigned_model,
            "model": assigned_model,
            "project": project,
            "status": "200 OK" if latency > 0 else "500 Failed",
            "tokens": int(fields.get("tokens", latency // 2)),
            "latency": latency,
            "ttft": ttft
        })

    return formatted_logs


@router.get("/config")
async def get_config(request: Request):
    """Retrieves current routing and model configurations."""
    cache = request.app.state.cache_layer
    config_json = await cache.get("gateway:config")
    if config_json:
        cfg = json.loads(config_json)
        cfg.pop("default_compression", None)
        return cfg
        
    # Default settings
    default_cfg = {
        "default_routing": {
            "mode": "auto",
            "simple_model": "fabric-speed-edge",
            "complex_model": "fabric-dense-reasoning"
        },
        "vendor_controls": {
            "deepseek": True,
            "gemini": True,
            "openai": True,
            "anthropic": True
        },
        "byok": {
            "enabled": True
        },
        "credentials": {
            "deepseek_key": "",
            "deepseek_base": "https://api.deepseek.com/v1",
            "gemini_key": "",
            "gemini_base": "https://generativelanguage.googleapis.com/v1beta",
            "openai_key": "",
            "openai_base": "https://api.openai.com/v1",
            "anthropic_key": "",
            "anthropic_base": "https://api.anthropic.com/v1"
        },
        "timeout": 30
    }
    return default_cfg


@router.post("/config")
async def save_config(config: dict, request: Request):
    """Saves new routing configurations."""
    cache = request.app.state.cache_layer
    await cache.set("gateway:config", json.dumps(config))
    return {"status": "saved"}


# --- Simulator Side-by-Side Streaming Logic ---

async def simulation_event_generator(req: SimulationRequest, client_auth_header: Optional[str], cache_client):
    """
    Executes calls to Model A and Model B in parallel.
    Streams back JSON events for both models to the frontend.
    """
    queue = asyncio.Queue()

    # Payload setup
    messages = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": req.user_message})

    async def run_model_stream(model_key: str, label: str):
        payload = {
            "model": model_key,
            "messages": messages,
            "stream": req.stream
        }
        start = time.time()
        ttft = None
        
        try:
            if not req.stream:
                res = await non_stream_forwarder(model_key, payload, client_auth_header, cache_client)
                content = res["choices"][0]["message"]["content"]
                latency = int((time.time() - start) * 1000)
                cost = 0.0002 if "speed" in model_key or "deepseek" in model_key else 0.003 if "claude" in model_key or "anthropic" in model_key else 0.0015
                tokens = len(content) // 4 + len(req.user_message) // 4
                await queue.put({
                    "model": label,
                    "content": content,
                    "done": True,
                    "cost": round(cost, 6),
                    "tokens": tokens,
                    "latency": latency,
                    "ttft": latency
                })
            else:
                async for chunk in stream_forwarder(model_key, payload, client_auth_header, cache_client):
                    if not ttft:
                        ttft = int((time.time() - start) * 1000)
                    
                    chunk_str = chunk.decode("utf-8", errors="ignore")
                    for line in chunk_str.split("\n"):
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                text = data["choices"][0]["delta"].get("content", "")
                                if text:
                                    await queue.put({"model": label, "content": text, "done": False})
                            except Exception:
                                pass
                
                latency = int((time.time() - start) * 1000)
                cost = 0.0002 if "speed" in model_key or "deepseek" in model_key else 0.003 if "claude" in model_key or "anthropic" in model_key else 0.0015
                await queue.put({
                    "model": label,
                    "content": "",
                    "done": True,
                    "cost": round(cost, 6),
                    "tokens": 400,
                    "latency": latency,
                    "ttft": ttft
                })
        except Exception as e:
            await queue.put({
                "model": label,
                "content": f"\nError calling provider: {str(e)}",
                "done": True,
                "cost": 0.0,
                "tokens": 0,
                "latency": int((time.time() - start) * 1000),
                "ttft": 0
            })

    # Schedule tasks in parallel
    task_a = asyncio.create_task(run_model_stream(req.model_a, "A"))
    task_b = asyncio.create_task(run_model_stream(req.model_b, "B"))

    done_count = 0
    while done_count < 2:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=15.0)
            yield f"data: {json.dumps(item)}\n\n"
            if item.get("done"):
                done_count += 1
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'error': 'Simulation stream timeout', 'done': True})}\n\n"
            break

    await task_a
    await task_b


@router.post("/simulate")
async def run_simulation(req: SimulationRequest, request: Request):
    """Executes the simulation streaming response."""
    auth_header = request.headers.get("Authorization")
    cache_layer = request.app.state.cache_layer
    
    if req.stream:
        return StreamingResponse(
            simulation_event_generator(req, auth_header, cache_layer),
            media_type="text/event-stream"
        )
    else:
        results = {"A": {"content": ""}, "B": {"content": ""}}
        async for sse in simulation_event_generator(req, auth_header, cache_layer):
            if sse.startswith("data: "):
                data = json.loads(sse[6:].strip())
                lbl = data.get("model")
                if lbl:
                    if data.get("done"):
                        results[lbl].update(data)
                    else:
                        results[lbl]["content"] += data.get("content", "")
                        
        return JSONResponse(content=results)
