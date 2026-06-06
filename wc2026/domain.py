"""Core domain types shared across ingest, models, and simulation.

Kept dependency-light (stdlib + numpy) so the simulation hot path and the tests stay
fast and the types are reusable by a future FastAPI layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CONFEDERATIONS = ("UEFA", "CONMEBOL", "CONCACAF", "CAF", "AFC", "OFC")
HOST_COUNTRIES = ("MEX", "USA", "CAN")
GROUP_LABELS = tuple("ABCDEFGHIJKL")  # A..L, 12 groups


@dataclass(frozen=True, slots=True)
class Team:
    name: str
    confederation: str
    elo_seed: float = 1500.0
    host: bool = False


@dataclass(frozen=True, slots=True)
class Venue:
    city: str
    country: str
    stadium: str
    altitude_m: float
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class Fixture:
    """A scheduled 2026 group match. ``home``/``away`` are *nominal* designations;
    the World Cup is played at neutral/host venues (``neutral`` reflects host advantage).
    """

    match_id: str
    group: str
    matchday: int  # 1..3
    home: str
    away: str
    date: str  # ISO date (YYYY-MM-DD); seed value, verify vs official
    venue_city: str
    neutral: bool = True  # True unless a host plays in its own country


@dataclass(slots=True)
class MatchContext:
    """Pre-kickoff context passed to ``predict_match`` (no leakage)."""

    neutral: bool = True
    altitude_m: float = 0.0
    home_country: str | None = None
    away_country: str | None = None
    venue_country: str | None = None
    rest_days_home: float | None = None
    rest_days_away: float | None = None
    travel_km_home: float | None = None
    travel_km_away: float | None = None
    # Generic additive adjustments to the log goal rates, injected by the feature layer
    # (altitude, host effect, travel/rest). The model applies them without needing to
    # know their provenance, keeping feature engineering and the model decoupled.
    home_logit_adj: float = 0.0
    away_logit_adj: float = 0.0
    # Which data tier produced the inputs (for the UI badge / provenance).
    data_tier: str = "tier0"


@dataclass(slots=True)
class GroupStanding:
    """One team's row in a computed group table."""

    team: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0
    points: int = 0
    fair_play: int = 0  # disciplinary points (lower = better); seed 0
    rank: int = 0  # 1..4 within group after tiebreakers

    @property
    def gd(self) -> int:
        return self.gf - self.ga


@dataclass(slots=True)
class MatchResult:
    home: str
    away: str
    home_goals: int
    away_goals: int
    group: str | None = None


@dataclass(slots=True)
class TournamentSpec:
    """The full 2026 group-stage structure: teams, groups, venues, fixtures."""

    teams: dict[str, Team]
    groups: dict[str, list[str]]  # label -> [team names]
    venues: dict[str, Venue]
    fixtures: list[Fixture] = field(default_factory=list)

    def team(self, name: str) -> Team:
        return self.teams[name]

    def group_of(self, team: str) -> str:
        for label, members in self.groups.items():
            if team in members:
                return label
        raise KeyError(f"team not in any group: {team}")
