"""Common ingest interface: provenance, caching, graceful fallback."""

from __future__ import annotations

import datetime as dt
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

USER_AGENT = "wc2026-predictor/0.1 (research; respects robots.txt & rate limits)"


@dataclass(slots=True)
class Provenance:
    """Where a record came from and when — logged for every ingested dataset."""

    source: str  # human-readable source name
    url: str | None  # fetch URL (None for seed/cached)
    tier: str  # tier0 | tier1 | tier2 | seed
    fetched_at: str  # ISO timestamp
    note: str = ""

    @staticmethod
    def now_iso() -> str:
        return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


@dataclass(slots=True)
class IngestResult:
    data: Any
    provenance: Provenance
    extra: dict[str, Any] = field(default_factory=dict)


def http_get(url: str, timeout: float = 20.0) -> bytes:
    """Fetch a URL with a polite User-Agent. Raises on failure (caller handles fallback)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted hosts)
        return resp.read()


def cache_path(cache_dir: Path, name: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / name
