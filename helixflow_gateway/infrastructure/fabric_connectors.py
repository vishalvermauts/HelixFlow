"""Asynchronous HTTP protocol translation gateway client.

Provides a streaming forwarder that proxies downstream token streams
from external fabric endpoints using non-blocking I/O and connection pooling.
"""
import httpx
from typing import AsyncGenerator
from helixflow_gateway.env_spec import runtime_settings


async def stream_forwarder(target_model: str, payload: dict) -> AsyncGenerator[bytes, None]:
    """
    Establishes connection handles directly to the backend downstream cluster.
    Streams token blocks chunk-by-chunk using non-blocking I/O.
    """
    url = f"{runtime_settings.DEFAULT_FABRIC_URL}/chat/completions"
    headers = {"Content-Type": "application/json"}

    pool_limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    timeout = runtime_settings.UPSTREAM_TIMEOUT_SEC

    async with httpx.AsyncClient(limits=pool_limits, timeout=timeout) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code != 200:
                err = f"data: {{\"transit_error\": \"Downstream response failed code {response.status_code}\"}}\n\n"
                yield err.encode()
                return

            async for raw_bytes in response.aiter_bytes():
                yield raw_bytes

