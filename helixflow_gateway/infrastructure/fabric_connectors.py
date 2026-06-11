import httpx
import json
from typing import AsyncGenerator, Optional
from helixflow_gateway.env_spec import runtime_settings

async def resolve_upstream(target_model: str, client_auth_header: Optional[str] = None, cache_client=None) -> tuple[str, dict, str]:
    """
    Resolves the upstream API endpoint, authorization headers, and model name.
    Returns: (url, headers, model_name)
    """
    # Load default settings from environment variables
    ds_key = runtime_settings.DEEPSEEK_API_KEY
    ds_base = runtime_settings.DEEPSEEK_API_BASE
    gem_key = runtime_settings.GEMINI_API_KEY
    gem_base = runtime_settings.GEMINI_API_BASE
    
    # Popular additional provider keys
    oa_key = ""
    oa_base = "https://api.openai.com/v1"
    ant_key = ""
    ant_base = "https://api.anthropic.com/v1"

    # Try loading dynamic configurations from Redis
    deepseek_enabled = True
    gemini_enabled = True
    openai_enabled = True
    anthropic_enabled = True

    if cache_client:
        try:
            config_json = await cache_client.get("gateway:config")
            if config_json:
                config = json.loads(config_json)
                credentials = config.get("credentials", {})
                if credentials.get("deepseek_key"):
                    ds_key = credentials["deepseek_key"]
                if credentials.get("deepseek_base"):
                    ds_base = credentials["deepseek_base"]
                if credentials.get("gemini_key"):
                    gem_key = credentials["gemini_key"]
                if credentials.get("gemini_base"):
                    gem_base = credentials["gemini_base"]
                
                # Load new keys
                oa_key = credentials.get("openai_key", oa_key)
                oa_base = credentials.get("openai_base", oa_base)
                ant_key = credentials.get("anthropic_key", ant_key)
                ant_base = credentials.get("anthropic_base", ant_base)

                vendor_controls = config.get("vendor_controls", {})
                deepseek_enabled = vendor_controls.get("deepseek", True)
                gemini_enabled = vendor_controls.get("gemini", True)
                openai_enabled = vendor_controls.get("openai", True)
                anthropic_enabled = vendor_controls.get("anthropic", True)
        except Exception:
            pass

    # Dynamic fallback based on vendor enablement
    if not deepseek_enabled and gemini_enabled and target_model == "fabric-speed-edge":
        target_model = "fabric-dense-reasoning"
    elif not gemini_enabled and deepseek_enabled and target_model == "fabric-dense-reasoning":
        target_model = "fabric-speed-edge"
    elif not anthropic_enabled and target_model == "fabric-anthropic-claude":
        target_model = "fabric-dense-reasoning"

    # Construct request details
    headers = {"Content-Type": "application/json"}
    model_name = target_model

    if target_model == "fabric-speed-edge":
        url = f"{ds_base.rstrip('/')}/chat/completions"
        if ds_key:
            headers["Authorization"] = f"Bearer {ds_key}"
        elif client_auth_header:
            headers["Authorization"] = client_auth_header
        model_name = "deepseek-chat"
        
    elif target_model == "fabric-dense-reasoning":
        if gem_key:
            base_url = gem_base.rstrip('/')
            if "aiplatform.googleapis.com" in base_url:
                url = f"{base_url}/endpoints/openapi/chat/completions?key={gem_key}"
                model_name = "google/gemini-2.5-pro"
            elif "generativelanguage.googleapis.com" in base_url and "/openai" not in base_url:
                url = f"{base_url}/openai/chat/completions"
                headers["Authorization"] = f"Bearer {gem_key}"
                model_name = "gemini-2.5-pro"
            else:
                url = f"{base_url}/chat/completions"
                headers["Authorization"] = f"Bearer {gem_key}"
                model_name = "gemini-2.5-pro"
        else:
            url = f"{ds_base.rstrip('/')}/chat/completions"
            if ds_key:
                headers["Authorization"] = f"Bearer {ds_key}"
            elif client_auth_header:
                headers["Authorization"] = client_auth_header
            model_name = "deepseek-chat"


    elif target_model.startswith("gpt-") or target_model.startswith("o1-") or target_model.startswith("o3-") or "openai" in target_model or target_model in ("fabric-openai-gpt4o", "fabric-openai-gpt4o-mini"):
        url = f"{oa_base.rstrip('/')}/chat/completions"
        if target_model == "fabric-openai-gpt4o":
            model_name = "gpt-4o"
        elif target_model == "fabric-openai-gpt4o-mini":
            model_name = "gpt-4o-mini"
        if oa_key:
            headers["Authorization"] = f"Bearer {oa_key}"
        elif client_auth_header:
            headers["Authorization"] = client_auth_header

    elif target_model.startswith("claude-") or "anthropic" in target_model:
        if target_model == "fabric-anthropic-claude":
            model_name = "claude-sonnet-4-6"
        base_url = ant_base.rstrip('/')
        if "api.anthropic.com" in base_url:
            # Strip trailing /v1 if present to avoid /v1/v1/messages
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]
            url = f"{base_url}/v1/messages"
            if ant_key:
                headers["x-api-key"] = ant_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            url = f"{base_url}/chat/completions"
            if ant_key:
                headers["Authorization"] = f"Bearer {ant_key}"
            elif client_auth_header:
                headers["Authorization"] = client_auth_header

    else:
        url = f"{runtime_settings.DEFAULT_FABRIC_URL.rstrip('/')}/chat/completions"
        if client_auth_header:
            headers["Authorization"] = client_auth_header

    return url, headers, model_name


def _to_anthropic_payload(payload: dict) -> dict:
    """Convert OpenAI chat/completions format to Anthropic Messages API format."""
    messages = payload.get("messages", [])
    system_text = ""
    user_messages = []
    for m in messages:
        if m.get("role") == "system":
            system_text += m.get("content", "")
        else:
            user_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    if not user_messages:
        user_messages = [{"role": "user", "content": "hello"}]
    anthropic_payload = {
        "model": payload.get("model", "claude-sonnet-4-6"),
        "max_tokens": payload.get("max_tokens", 4096),
        "messages": user_messages,
    }
    if system_text:
        anthropic_payload["system"] = system_text
    return anthropic_payload


def _from_anthropic_response(resp_data: dict) -> dict:
    """Convert Anthropic Messages API response to OpenAI chat/completions format."""
    content_blocks = resp_data.get("content", [])
    text = ""
    for block in content_blocks:
        if block.get("type") == "text":
            text += block.get("text", "")
    usage = resp_data.get("usage", {})
    return {
        "id": resp_data.get("id", ""),
        "object": "chat.completion",
        "model": resp_data.get("model", "claude-sonnet-4-6"),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": resp_data.get("stop_reason", "stop"),
        }],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        },
    }


async def stream_forwarder(
    target_model: str, payload: dict, client_auth_header: Optional[str] = None, cache_client=None
) -> AsyncGenerator[bytes, None]:
    """
    Establishes connection handles directly to the backend downstream cluster.
    Streams token blocks chunk-by-chunk using non-blocking I/O.
    """
    url, headers, model_name = await resolve_upstream(target_model, client_auth_header, cache_client)
    payload["model"] = model_name

    # Transform payload for Anthropic Messages API (streaming not yet supported for Anthropic)
    is_anthropic = "api.anthropic.com" in url
    if is_anthropic:
        send_payload = _to_anthropic_payload(payload)
    else:
        send_payload = payload

    pool_limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    timeout = runtime_settings.UPSTREAM_TIMEOUT_SEC

    async with httpx.AsyncClient(limits=pool_limits, timeout=timeout) as client:
        async with client.stream("POST", url, json=send_payload, headers=headers) as response:
            if response.status_code != 200:
                err_text = await response.aread()
                err = f"data: {{\"transit_error\": \"Downstream response failed code {response.status_code}: {err_text.decode('utf-8', errors='ignore')}\"}}\n\n"
                yield err.encode()
                return

            async for line in response.aiter_lines():
                yield (line + "\n").encode("utf-8")


async def non_stream_forwarder(
    target_model: str, payload: dict, client_auth_header: Optional[str] = None, cache_client=None
) -> dict:
    """
    Establishes connection handles directly to the backend downstream cluster.
    Sends standard chat completion requests and returns the parsed JSON response.
    """
    url, headers, model_name = await resolve_upstream(target_model, client_auth_header, cache_client)
    payload["model"] = model_name

    # Transform payload for Anthropic Messages API
    is_anthropic = "api.anthropic.com" in url
    if is_anthropic:
        send_payload = _to_anthropic_payload(payload)
    else:
        send_payload = payload

    pool_limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    timeout = runtime_settings.UPSTREAM_TIMEOUT_SEC

    async with httpx.AsyncClient(limits=pool_limits, timeout=timeout) as client:
        response = await client.post(url, json=send_payload, headers=headers)
        response.raise_for_status()
        resp_data = response.json()

        # Convert Anthropic response back to OpenAI format
        if is_anthropic:
            return _from_anthropic_response(resp_data)
        return resp_data


