"""Deterministic research-only stock opportunity analysis."""

from .features import compute_features
from .models import TechnicalFeatures

__all__ = ["TechnicalFeatures", "compute_features"]
