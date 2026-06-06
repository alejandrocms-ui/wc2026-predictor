"""Build data/seed/fixtures.json from the official 2026 group-stage schedule.

Source: official 2026 World Cup group-stage fixtures (match numbers, dates, venues) as
verified Dec 2025 (ESPN/Wikipedia/FIFA draw). Match numbers, dates, fixtures and venues are
HIGH confidence; exact kickoff times are NOT included here (flagged as unverified).

Run: python scripts/build_official_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "seed"

# (match_no, "Mon DD", home, away, city) — first team is the Team A / nominal home.
MATCHES = [
    # Matchday 1 (1–24)
    (1, "Jun 11", "Mexico", "South Africa", "Mexico City"),
    (2, "Jun 11", "Korea Republic", "Czechia", "Guadalajara"),
    (3, "Jun 12", "Canada", "Bosnia and Herzegovina", "Toronto"),
    (4, "Jun 12", "United States", "Paraguay", "Los Angeles"),
    (5, "Jun 13", "Qatar", "Switzerland", "San Francisco Bay Area"),
    (6, "Jun 13", "Brazil", "Morocco", "New York New Jersey"),
    (7, "Jun 13", "Haiti", "Scotland", "Boston"),
    (8, "Jun 13", "Australia", "Türkiye", "Vancouver"),
    (9, "Jun 14", "Germany", "Curaçao", "Houston"),
    (10, "Jun 14", "Netherlands", "Japan", "Dallas"),
    (11, "Jun 14", "Côte d'Ivoire", "Ecuador", "Philadelphia"),
    (12, "Jun 14", "Sweden", "Tunisia", "Monterrey"),
    (13, "Jun 15", "Spain", "Cabo Verde", "Atlanta"),
    (14, "Jun 15", "Belgium", "Egypt", "Seattle"),
    (15, "Jun 15", "Saudi Arabia", "Uruguay", "Miami"),
    (16, "Jun 15", "Iran", "New Zealand", "Los Angeles"),
    (17, "Jun 16", "France", "Senegal", "New York New Jersey"),
    (18, "Jun 16", "Iraq", "Norway", "Boston"),
    (19, "Jun 16", "Argentina", "Algeria", "Kansas City"),
    (20, "Jun 16", "Austria", "Jordan", "San Francisco Bay Area"),
    (21, "Jun 17", "Portugal", "Congo DR", "Houston"),
    (22, "Jun 17", "England", "Croatia", "Dallas"),
    (23, "Jun 17", "Ghana", "Panama", "Toronto"),
    (24, "Jun 17", "Uzbekistan", "Colombia", "Mexico City"),
    # Matchday 2 (25–48)
    (25, "Jun 18", "Czechia", "South Africa", "Atlanta"),
    (26, "Jun 18", "Switzerland", "Bosnia and Herzegovina", "Los Angeles"),
    (27, "Jun 18", "Canada", "Qatar", "Vancouver"),
    (28, "Jun 18", "Mexico", "Korea Republic", "Guadalajara"),
    (29, "Jun 19", "United States", "Australia", "Seattle"),
    (30, "Jun 19", "Scotland", "Morocco", "Boston"),
    (31, "Jun 19", "Brazil", "Haiti", "Philadelphia"),
    (32, "Jun 19", "Türkiye", "Paraguay", "San Francisco Bay Area"),
    (33, "Jun 20", "Netherlands", "Sweden", "Houston"),
    (34, "Jun 20", "Germany", "Côte d'Ivoire", "Toronto"),
    (35, "Jun 20", "Ecuador", "Curaçao", "Kansas City"),
    (36, "Jun 20", "Tunisia", "Japan", "Monterrey"),
    (37, "Jun 21", "Spain", "Saudi Arabia", "Atlanta"),
    (38, "Jun 21", "Belgium", "Iran", "Los Angeles"),
    (39, "Jun 21", "Uruguay", "Cabo Verde", "Miami"),
    (40, "Jun 21", "New Zealand", "Egypt", "Vancouver"),
    (41, "Jun 22", "Argentina", "Austria", "Dallas"),
    (42, "Jun 22", "France", "Iraq", "Philadelphia"),
    (43, "Jun 22", "Norway", "Senegal", "New York New Jersey"),
    (44, "Jun 22", "Jordan", "Algeria", "San Francisco Bay Area"),
    (45, "Jun 23", "Portugal", "Uzbekistan", "Houston"),
    (46, "Jun 23", "England", "Ghana", "Boston"),
    (47, "Jun 23", "Panama", "Croatia", "Toronto"),
    (48, "Jun 23", "Colombia", "Congo DR", "Guadalajara"),
    # Matchday 3 (49–72) — simultaneous kickoffs per group
    (49, "Jun 24", "Switzerland", "Canada", "Vancouver"),
    (50, "Jun 24", "Bosnia and Herzegovina", "Qatar", "Seattle"),
    (51, "Jun 24", "Scotland", "Brazil", "Miami"),
    (52, "Jun 24", "Morocco", "Haiti", "Atlanta"),
    (53, "Jun 24", "Czechia", "Mexico", "Mexico City"),
    (54, "Jun 24", "South Africa", "Korea Republic", "Monterrey"),
    (55, "Jun 25", "Ecuador", "Germany", "New York New Jersey"),
    (56, "Jun 25", "Curaçao", "Côte d'Ivoire", "Philadelphia"),
    (57, "Jun 25", "Japan", "Sweden", "Dallas"),
    (58, "Jun 25", "Tunisia", "Netherlands", "Kansas City"),
    (59, "Jun 25", "Türkiye", "United States", "Los Angeles"),
    (60, "Jun 25", "Paraguay", "Australia", "San Francisco Bay Area"),
    (61, "Jun 26", "Norway", "France", "Boston"),
    (62, "Jun 26", "Senegal", "Iraq", "Toronto"),
    (63, "Jun 26", "Cabo Verde", "Saudi Arabia", "Houston"),
    (64, "Jun 26", "Uruguay", "Spain", "Guadalajara"),
    (65, "Jun 26", "Egypt", "Iran", "Seattle"),
    (66, "Jun 26", "New Zealand", "Belgium", "Vancouver"),
    (67, "Jun 27", "Panama", "England", "New York New Jersey"),
    (68, "Jun 27", "Croatia", "Ghana", "Philadelphia"),
    (69, "Jun 27", "Colombia", "Portugal", "Miami"),
    (70, "Jun 27", "Congo DR", "Uzbekistan", "Atlanta"),
    (71, "Jun 27", "Algeria", "Austria", "Kansas City"),
    (72, "Jun 27", "Jordan", "Argentina", "Dallas"),
]

_MONTHS = {"Jun": "06", "Jul": "07"}


def main() -> None:
    groups = json.loads((SEED / "groups.json").read_text(encoding="utf-8"))["groups"]
    team_group = {t: g for g, members in groups.items() for t in members}

    fixtures = []
    for num, date_str, home, away, city in MATCHES:
        assert team_group.get(home) == team_group.get(away), (
            f"match {num}: {home} ({team_group.get(home)}) vs {away} "
            f"({team_group.get(away)}) not in same group"
        )
        mon, day = date_str.split()
        iso = f"2026-{_MONTHS[mon]}-{int(day):02d}"
        matchday = 1 if num <= 24 else (2 if num <= 48 else 3)
        fixtures.append(
            {
                "match_id": f"M{num:02d}",
                "match_no": num,
                "group": team_group[home],
                "matchday": matchday,
                "home": home,
                "away": away,
                "date": iso,
                "venue_city": city,
            }
        )

    out = {
        "_provenance": {
            "source": "Official 2026 FIFA World Cup group-stage schedule (verified Dec 2025: "
            "match numbers, dates, fixtures, venues). Kickoff times NOT included (unverified).",
            "as_of": "2026-06-05",
            "confidence": "HIGH for fixtures/dates/venues; kickoff times omitted",
        },
        "fixtures": fixtures,
    }
    path = SEED / "fixtures.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    # Validation: 72 matches, 6 per group, each team 3 games.
    assert len(fixtures) == 72, len(fixtures)
    from collections import Counter

    per_team = Counter()
    for f in fixtures:
        per_team[f["home"]] += 1
        per_team[f["away"]] += 1
    assert all(v == 3 for v in per_team.values()), per_team
    assert len(per_team) == 48, len(per_team)
    print(f"wrote {path} — 72 fixtures, validated (6/group, 3/team, 48 teams)")


if __name__ == "__main__":
    main()
