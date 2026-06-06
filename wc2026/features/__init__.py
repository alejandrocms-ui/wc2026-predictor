"""Leakage-safe feature builders. Every feature is computed as-of pre-kickoff.

See ``FEATURES.md`` for the catalogue, each feature's source tier, and its leakage check.
"""

from .context import build_context

__all__ = ["build_context"]
