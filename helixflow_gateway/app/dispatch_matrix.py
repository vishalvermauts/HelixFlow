"""Closed-form model routing analytics mapping logic (NumPy).

This module provides a small example mapping function used by the
dispatching/routing logic in the gateway.
"""
import numpy as np


def score_models(feature_vector: np.ndarray, weight_matrix: np.ndarray) -> np.ndarray:
    """Compute simple scores for available models.

    Args:
        feature_vector: 1D feature vector.
        weight_matrix: 2D matrix where each row is a model weight vector.

    Returns:
        1D array of scores.
    """
    return weight_matrix.dot(feature_vector)
