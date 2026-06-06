"""Data ingestion adapters, tiered by cost, behind a common interface.

Every adapter returns an :class:`IngestResult` carrying the data plus provenance (source
URL/name + fetch timestamp + tier). Adapters cache aggressively and degrade gracefully:
if a source is unreachable (or ``WC2026_OFFLINE=true``), they fall back to a cached snapshot
or the committed seed, and report which tier actually produced the data so the UI can badge
it. The app is guaranteed to run end-to-end on Tier-0 with zero keys.
"""

from .base import IngestResult, Provenance
from .elo import EloRatingsAdapter
from .historical import HistoricalResultsAdapter

__all__ = [
    "IngestResult",
    "Provenance",
    "HistoricalResultsAdapter",
    "EloRatingsAdapter",
]
