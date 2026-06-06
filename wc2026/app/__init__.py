"""Streamlit MVP — a thin presentation layer over the wc2026 library.

The app reads precomputed predictions/simulations from the DuckDB store (fast, offline) and
can also live-predict an arbitrary match via the cached model. No modelling logic lives
here — see ``wc2026.engine`` / ``wc2026.models`` — so a future FastAPI + React front end can
reuse the exact same library calls.
"""
