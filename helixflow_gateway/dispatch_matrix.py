import json
import numpy as np
from typing import List, Optional
from helixflow_gateway.contracts import MessageContract

# Provider priority order (first available wins for each tier)
# Tier 0: Speed/cheap  — DeepSeek > OpenAI mini
# Tier 1: Reasoning    — Gemini Pro > OpenAI GPT-4o > Anthropic > DeepSeek
# Tier 2: Agent/code   — Anthropic > OpenAI GPT-4o > Gemini Pro

PROVIDER_TIERS = {
    "speed":     ["fabric-speed-edge", "fabric-openai-gpt4o-mini"],
    "reasoning": ["fabric-dense-reasoning", "fabric-openai-gpt4o", "fabric-anthropic-claude", "fabric-speed-edge"],
    "agent":     ["fabric-anthropic-claude", "fabric-openai-gpt4o", "fabric-dense-reasoning"],
}

FABRIC_KEY_MAP = {
    "fabric-speed-edge":        "deepseek",
    "fabric-dense-reasoning":   "gemini",
    "fabric-anthropic-claude":  "anthropic",
    "fabric-openai-gpt4o":      "openai",
    "fabric-openai-gpt4o-mini": "openai",
}


async def get_available_providers(cache_client=None) -> dict:
    """
    Reads gateway:config from Redis and returns a dict of configured provider keys.
    Returns: { "deepseek": "sk-...", "gemini": "AI...", "anthropic": "sk-ant-...", "openai": "sk-..." }
    """
    available = {}
    if not cache_client:
        return available
    try:
        config_json = await cache_client.get("gateway:config")
        if config_json:
            config = json.loads(config_json)
            creds = config.get("credentials", {})
            controls = config.get("vendor_controls", {})
            if creds.get("deepseek_key") and controls.get("deepseek", True):
                available["deepseek"] = creds["deepseek_key"]
            gem_key = creds.get("gemini_key", "")
            # Accept both standard API keys (AIza...) and Vertex AI refresh tokens (AQ.)
            if gem_key and controls.get("gemini", True):
                available["gemini"] = gem_key
            if creds.get("anthropic_key") and controls.get("anthropic", True):
                available["anthropic"] = creds["anthropic_key"]
            if creds.get("openai_key") and controls.get("openai", True):
                available["openai"] = creds["openai_key"]
    except Exception:
        pass
    return available


def _select_from_tier(tier: str, available_providers: dict) -> str:
    """Pick the first fabric key in the tier that has a configured API key."""
    for fabric_key in PROVIDER_TIERS[tier]:
        provider = FABRIC_KEY_MAP.get(fabric_key)
        if provider and provider in available_providers:
            return fabric_key
    # Last-resort: return first in tier regardless
    return PROVIDER_TIERS[tier][0]


def calculate_routing_score(messages: List[MessageContract], available_providers: Optional[dict] = None) -> str:
    """
    Selects a fabric key based on:
      1. Which providers have API keys configured (from Redis)
      2. Message complexity (length + keyword heuristic)
    Returns the selected fabric key.
    """
    if available_providers is None:
        available_providers = {}

    total_tokens = sum(len(m.content) for m in messages)
    avg_tokens = total_tokens / max(1, len(messages))

    if avg_tokens >= 800:
        tier = "reasoning"
    elif avg_tokens >= 200:
        combined = " ".join(m.content.lower() for m in messages)
        agent_kw = ["write a", "build", "create", "generate", "agent", "script", "bot", "code", "implement"]
        tier = "agent" if any(kw in combined for kw in agent_kw) else "reasoning"
    else:
        tier = "speed"

    return _select_from_tier(tier, available_providers)


async def calculate_routing_score_async(messages: List[MessageContract], cache_client=None) -> str:
    """
    Async version — fetches provider availability from Redis then routes.
    Use this from FastAPI async handlers.
    """
    available = await get_available_providers(cache_client)
    return calculate_routing_score(messages, available)
