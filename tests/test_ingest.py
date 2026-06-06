"""Ingest tests: offline seed fallback, name normalization, Elo sanity, no-leakage."""

from __future__ import annotations

import pandas as pd

from wc2026.config import get_settings
from wc2026.ingest.elo import compute_elo
from wc2026.ingest.historical import HistoricalResultsAdapter, normalize_team


def test_name_normalization_maps_to_canonical():
    assert normalize_team("South Korea") == "Korea Republic"
    assert normalize_team("Czech Republic") == "Czechia"
    assert normalize_team("Ivory Coast") == "Côte d'Ivoire"
    assert normalize_team("Turkey") == "Türkiye"
    assert normalize_team("Brazil") == "Brazil"  # unchanged


def test_offline_falls_back_to_seed_sample():
    s = get_settings()
    adapter = HistoricalResultsAdapter(s.cache_dir, s.seed_dir, offline=True)
    res = adapter.load()
    df = res.data
    assert not df.empty
    assert {"date", "home", "away", "home_score", "away_score", "neutral"} <= set(df.columns)
    assert res.provenance.tier in {"tier0", "seed"}  # cached snapshot or committed seed


def test_elo_rewards_winning_and_is_zero_sum_per_match():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
            "home": ["A", "A", "A"],
            "away": ["B", "B", "B"],
            "home_score": [3, 2, 1],
            "away_score": [0, 0, 0],
            "neutral": [True, True, True],
            "tournament": ["Friendly"] * 3,
        }
    )
    elo = compute_elo(df)
    assert elo["A"] > 1500 > elo["B"]
    # Each match transfers points symmetrically -> total stays ~constant.
    assert abs((elo["A"] + elo["B"]) - 3000.0) < 1e-6


def test_elo_as_of_excludes_future_matches_no_leakage():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2025-01-01"]),
            "home": ["A", "A"],
            "away": ["B", "B"],
            "home_score": [5, 0],
            "away_score": [0, 5],
            "neutral": [True, True],
            "tournament": ["Friendly", "Friendly"],
        }
    )
    # As-of 2024-06 only the first (A win) match counts -> A clearly rated above B.
    elo = compute_elo(df, as_of="2024-06-01")
    assert elo["A"] > elo["B"]
    a_gap_asof = elo["A"] - elo["B"]
    # With the future (B-win) match included the gap shrinks dramatically -> the as-of
    # computation genuinely excluded later data (no leakage). Elo is path-dependent, so
    # the two 5-0 results need not net to exactly equal.
    elo_full = compute_elo(df)
    assert abs(elo_full["A"] - elo_full["B"]) < a_gap_asof / 5
