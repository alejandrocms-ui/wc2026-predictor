"""Tier-0 historical international results — the modelling backbone.

Source: the open "International football results from 1872 to present" dataset
(martj42/international_results), CSV, public domain-ish / CC0-style community data. We fetch
``results.csv``, normalise team names to our canonical set, cache to Parquet, and expose a
tidy frame with columns ``[date, home, away, home_score, away_score, neutral, tournament,
city, country]``. Full history is retained; the model applies exponential time decay.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from .base import IngestResult, Provenance, cache_path, http_get

RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)

# Map dataset team names -> our canonical 2026 names (only where they differ).
CANONICAL_NAMES: dict[str, str] = {
    "South Korea": "Korea Republic",
    "Czech Republic": "Czechia",
    "DR Congo": "Congo DR",
    "Cape Verde": "Cabo Verde",
    "Ivory Coast": "Côte d'Ivoire",
    "Turkey": "Türkiye",
    "United States": "United States",
    "Curacao": "Curaçao",
    "Republic of Ireland": "Ireland",
}


def normalize_team(name: str) -> str:
    return CANONICAL_NAMES.get(name, name)


def _parse_csv(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw))
    df = df.rename(
        columns={
            "home_team": "home",
            "away_team": "away",
        }
    )
    df["home"] = df["home"].map(normalize_team)
    df["away"] = df["away"].map(normalize_team)
    keep = ["date", "home", "away", "home_score", "away_score", "neutral", "tournament", "city", "country"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "home_score", "away_score"])
    if df["neutral"].dtype != bool:
        df["neutral"] = df["neutral"].astype(str).str.lower().isin(["true", "1", "yes"])
    return df.reset_index(drop=True)


class HistoricalResultsAdapter:
    """Fetch (or load cached/seed) historical international results."""

    name = "International football results 1872–present (martj42)"
    tier = "tier0"

    def __init__(self, cache_dir: Path, seed_dir: Path, offline: bool = False):
        self.cache_dir = cache_dir
        self.seed_dir = seed_dir
        self.offline = offline
        self.cache_file = cache_path(cache_dir, "historical_results.parquet")
        self.seed_file = seed_dir / "historical_results_sample.csv"

    def load(self, force_refresh: bool = False) -> IngestResult:
        # 1) Live fetch (unless offline / cached and not forced).
        if not self.offline and (force_refresh or not self.cache_file.exists()):
            try:
                raw = http_get(RESULTS_URL)
                df = _parse_csv(raw)
                df.to_parquet(self.cache_file, index=False)
                prov = Provenance(
                    source=self.name,
                    url=RESULTS_URL,
                    tier="tier0",
                    fetched_at=Provenance.now_iso(),
                    note=f"{len(df)} matches",
                )
                return IngestResult(data=df, provenance=prov)
            except Exception as exc:  # network down -> fall through to cache/seed
                last_error = exc
        else:
            last_error = None

        # 2) Cached Parquet snapshot.
        if self.cache_file.exists():
            df = pd.read_parquet(self.cache_file)
            mtime = pd.Timestamp(self.cache_file.stat().st_mtime, unit="s").isoformat()
            prov = Provenance(
                source=self.name,
                url=None,
                tier="tier0",
                fetched_at=mtime,
                note=f"cached snapshot, {len(df)} matches",
            )
            return IngestResult(data=df, provenance=prov)

        # 3) Committed seed sample (guarantees offline operation in a fresh clone).
        if self.seed_file.exists():
            df = _parse_csv(self.seed_file.read_bytes())
            prov = Provenance(
                source=self.name + " [seed sample]",
                url=None,
                tier="seed",
                fetched_at="committed-seed",
                note=f"seed sample, {len(df)} matches; fetch for full history",
            )
            return IngestResult(data=df, provenance=prov)

        raise RuntimeError(
            f"No historical results available (offline={self.offline}); "
            f"last network error: {last_error!r}"
        )
