import numpy as np
from typing import List
from helixflow_gateway.contracts import MessageContract

# Pre-compiled multi-armed routing array weights
FABRIC_WEIGHTS = np.array([
    [0.8, 0.2],  # Option index 0: High speed edge execution engine
    [0.1, 0.9],  # Option index 1: High tier dense reasoning model
])

FABRIC_MAP = {
    0: "fabric-speed-edge",
    1: "fabric-dense-reasoning"
}


def calculate_routing_score(messages: List[MessageContract]) -> str:
    """
    Evaluates context thresholds using closed-form dot-product array math.
    Returns the selected fabric key.
    """
    # Lightweight heuristic to derive a 2-element intent vector from messages
    # (example: short messages favor speed, long messages favor reasoning)
    total_tokens = sum(len(m.content) for m in messages)
    avg_tokens = total_tokens / max(1, len(messages))

    if avg_tokens >= 500:
        intent_vector = np.array([0.2, 0.8])
    else:
        intent_vector = np.array([0.9, 0.1])

    scores = np.dot(FABRIC_WEIGHTS, intent_vector)
    selected_index = int(np.argmax(scores))
    return FABRIC_MAP.get(selected_index, "fabric-speed-edge")
