"""Build a leakage-safe :class:`MatchContext` for a 2026 fixture.

Context features here use ONLY information knowable before kickoff (venue, host status,
altitude, schedule) — never the match result. Richer form/xG features live in the model
fit (time-decayed historical results) and the optional GBM; this module covers the
match-level context that adjusts the Dixon-Coles log goal rates.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from ..domain import Fixture, MatchContext, TournamentSpec

# Nations whose players are broadly acclimatised to altitude (home leagues at height).
# Used to exempt them from the high-altitude suppression at venues like Mexico City.
_HIGH_ALTITUDE_NATIONS = frozenset({"Mexico", "Ecuador", "Bolivia", "Colombia"})

# Altitude at/above which we apply a suppression to non-acclimatised teams.
_ALTITUDE_THRESHOLD_M = 1500.0
# Max log-rate suppression at the highest venue (Mexico City ~2240 m). Small & documented.
_ALTITUDE_MAX_PENALTY = 0.06

# The three host nations and their venue country codes. A host playing in its own country
# gets a home-advantage boost — even when it is the nominal *away* team (the venue/crowd is
# still theirs), which the official schedule does produce (e.g. Switzerland v Canada in
# Vancouver). Additive log goal-rate boost ≈ exp(0.30) ≈ 1.35x scoring.
_HOST_COUNTRY = {"Mexico": "MEX", "United States": "USA", "Canada": "CAN"}
_HOST_ADVANTAGE_LOGIT = 0.30


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km (for travel-distance features)."""
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def build_context(
    fixture: Fixture,
    spec: TournamentSpec,
    *,
    data_tier: str = "tier0",
) -> MatchContext:
    """Construct the pre-kickoff context for one fixture."""
    venue = spec.venues.get(fixture.venue_city)
    altitude = venue.altitude_m if venue else 0.0

    venue_country = venue.country if venue else None
    ctx = MatchContext(
        neutral=fixture.neutral,
        altitude_m=altitude,
        venue_country=venue_country,
        data_tier=data_tier,
    )

    # Host advantage by venue country (applies to a host even as the nominal away team).
    if _HOST_COUNTRY.get(fixture.home) == venue_country and venue_country is not None:
        ctx.home_logit_adj += _HOST_ADVANTAGE_LOGIT
    if _HOST_COUNTRY.get(fixture.away) == venue_country and venue_country is not None:
        ctx.away_logit_adj += _HOST_ADVANTAGE_LOGIT

    # Altitude: suppress goal rates for non-acclimatised teams at high venues. The lowland
    # side fatigues faster; an acclimatised nation is exempt. Effect scales with altitude.
    if altitude >= _ALTITUDE_THRESHOLD_M:
        penalty = -_ALTITUDE_MAX_PENALTY * (altitude / 2240.0)
        if fixture.home not in _HIGH_ALTITUDE_NATIONS:
            ctx.home_logit_adj += penalty
        if fixture.away not in _HIGH_ALTITUDE_NATIONS:
            ctx.away_logit_adj += penalty

    return ctx
