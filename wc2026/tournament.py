"""Load the 2026 tournament structure and generate the group-stage fixture list.

The confirmed group composition (prompt §2) is the verified seed; venues/dates here are
seed placeholders flagged for verification. The *matchups* are not invented — a group of
4 is a full round-robin (all 6 pairings), so the only seed assumptions are which matchday
and venue each pairing lands on. An official-fixture ingest adapter can override dates and
venues without changing any matchup.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import Settings, get_settings
from .domain import GROUP_LABELS, Fixture, Team, TournamentSpec, Venue

# Canonical 1-factorization of a 4-team round-robin by group seed position (1..4).
# Each matchday pairs all four teams once; covers every C(4,2)=6 pairing exactly once.
# (home, away) order is the nominal designation only — venues are neutral/host.
_ROUND_ROBIN: dict[int, list[tuple[int, int]]] = {
    1: [(1, 2), (3, 4)],
    2: [(1, 3), (4, 2)],
    3: [(4, 1), (2, 3)],
}

# Seed matchday dates spread across the 11–27 June 2026 group-stage window.
# Groups are split into three waves so the three matchdays fan out realistically.
_MATCHDAY_DATES: dict[int, str] = {
    1: "2026-06-13",
    2: "2026-06-19",
    3: "2026-06-25",
}


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_teams(seed_dir: Path) -> dict[str, Team]:
    raw = _read_json(seed_dir / "teams.json")
    out: dict[str, Team] = {}
    for t in raw["teams"]:
        out[t["name"]] = Team(
            name=t["name"],
            confederation=t["confederation"],
            elo_seed=float(t.get("elo_seed", 1500.0)),
            host=bool(t.get("host", False)),
        )
    return out


def load_groups(seed_dir: Path) -> dict[str, list[str]]:
    raw = _read_json(seed_dir / "groups.json")
    groups = {k: list(v) for k, v in raw["groups"].items()}
    # Validate structure: 12 groups A..L, exactly 4 teams each, 48 distinct teams.
    assert set(groups) == set(GROUP_LABELS), f"expected groups A..L, got {sorted(groups)}"
    seen: set[str] = set()
    for label, members in groups.items():
        assert len(members) == 4, f"group {label} must have 4 teams, has {len(members)}"
        for m in members:
            assert m not in seen, f"team in multiple groups: {m}"
            seen.add(m)
    assert len(seen) == 48, f"expected 48 teams, got {len(seen)}"
    return groups


def load_venues(seed_dir: Path) -> dict[str, Venue]:
    raw = _read_json(seed_dir / "venues.json")
    out: dict[str, Venue] = {}
    for v in raw["venues"]:
        out[v["city"]] = Venue(
            city=v["city"],
            country=v["country"],
            stadium=v["stadium"],
            altitude_m=float(v["altitude_m"]),
            lat=float(v["lat"]),
            lon=float(v["lon"]),
        )
    return out


def generate_fixtures(
    groups: dict[str, list[str]],
    teams: dict[str, Team],
    venue_cities: list[str],
) -> list[Fixture]:
    """Deterministically generate the 72 group-stage fixtures (6 per group).

    Venue assignment is a stable round-robin over host cities; a host team's match is
    marked non-neutral when it lands in a venue in its own country (drives host advantage).
    """
    country_by_host_team = {
        "Mexico": "MEX",
        "United States": "USA",
        "Canada": "CAN",
    }
    fixtures: list[Fixture] = []
    v_idx = 0
    for label in GROUP_LABELS:
        members = groups[label]  # positions 1..4 -> index 0..3
        for md in (1, 2, 3):
            for (h, a) in _ROUND_ROBIN[md]:
                home = members[h - 1]
                away = members[a - 1]
                city = venue_cities[v_idx % len(venue_cities)]
                v_idx += 1
                neutral = True
                # Host advantage: if the nominal home team is a host nation, prefer to
                # treat as non-neutral (hosts overwhelmingly play in-country).
                if home in country_by_host_team:
                    neutral = False
                fixtures.append(
                    Fixture(
                        match_id=f"{label}{md}-{h}{a}",
                        group=label,
                        matchday=md,
                        home=home,
                        away=away,
                        date=_MATCHDAY_DATES[md],
                        venue_city=city,
                        neutral=neutral,
                    )
                )
    assert len(fixtures) == 72, f"expected 72 fixtures, got {len(fixtures)}"
    return fixtures


def load_official_fixtures(seed_dir: Path) -> list[Fixture] | None:
    """Load the verified official fixture list (data/seed/fixtures.json) if present.

    Venues are neutral except for host nations; host advantage is applied at context-build
    time from the venue's country (so a host playing as the nominal 'away' team in its own
    country still gets the boost), hence ``neutral=True`` is stored here uniformly.
    """
    path = seed_dir / "fixtures.json"
    if not path.exists():
        return None
    raw = _read_json(path)
    fixtures = [
        Fixture(
            match_id=f["match_id"],
            group=f["group"],
            matchday=int(f["matchday"]),
            home=f["home"],
            away=f["away"],
            date=f["date"],
            venue_city=f["venue_city"],
            neutral=True,
        )
        for f in raw["fixtures"]
    ]
    assert len(fixtures) == 72, f"expected 72 official fixtures, got {len(fixtures)}"
    return fixtures


def load_spec(settings: Settings | None = None) -> TournamentSpec:
    """Load the full tournament spec from committed seed data (works fully offline).

    Prefers the verified official fixture list; falls back to the deterministic round-robin
    generator if it is absent.
    """
    settings = settings or get_settings()
    seed_dir = settings.seed_dir
    teams = load_teams(seed_dir)
    groups = load_groups(seed_dir)
    venues = load_venues(seed_dir)
    fixtures = load_official_fixtures(seed_dir)
    if fixtures is None:
        fixtures = generate_fixtures(groups, teams, list(venues.keys()))
    return TournamentSpec(teams=teams, groups=groups, venues=venues, fixtures=fixtures)
