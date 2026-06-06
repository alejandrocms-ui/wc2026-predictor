"""Cached data/model loaders for the Streamlit app."""

from __future__ import annotations

import streamlit as st

from wc2026.config import get_settings
from wc2026.ingest.elo import compute_elo
from wc2026.ingest.historical import HistoricalResultsAdapter
from wc2026.models.build import build_dixon_coles
from wc2026.store import WC2026Store
from wc2026.tournament import load_spec


@st.cache_resource(show_spinner=False)
def get_spec():
    return load_spec(get_settings())


@st.cache_resource(show_spinner=False)
def get_store():
    return WC2026Store(get_settings().duckdb_path)


@st.cache_resource(show_spinner="Cargando modelo… / Loading model…")
def get_model():
    """Return the predictive model for live custom predictions.

    Prefers the exact model the pipeline trained (``data/model.pkl`` — the calibrated
    ensemble), so the match page agrees with the precomputed group/dashboard numbers. Falls
    back to a fast Dixon-Coles build from cached/seed data if no saved model exists.
    """
    settings = get_settings()
    model_path = settings.data_dir / "model.pkl"
    if model_path.exists():
        try:
            import joblib

            return joblib.load(model_path), "tier0"
        except Exception:
            pass
    spec = load_spec(settings)
    adapter = HistoricalResultsAdapter(settings.cache_dir, settings.seed_dir, offline=True)
    res = adapter.load()
    results = res.data
    elo = compute_elo(results)
    for name, team in spec.teams.items():
        elo.setdefault(name, team.elo_seed)
    model = build_dixon_coles(
        results, elo, halflife_days=settings.decay_halflife_days,
        teams_of_interest=list(spec.teams),
    )
    return model, res.provenance.tier


@st.cache_data(show_spinner=False)
def load_simulation_df():
    return get_store().load_simulation()


@st.cache_data(show_spinner=False)
def load_predictions_df():
    return get_store().load_predictions()


@st.cache_data(show_spinner=False)
def load_provenance_df():
    return get_store().load_provenance()
