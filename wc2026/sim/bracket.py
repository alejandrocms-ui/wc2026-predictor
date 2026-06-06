"""Round-of-32 bracket mapping for the 48-team format.

The 2026 R32 pairings for group winners and runners-up are fixed, but the slots filled by
the 8 best third-placed teams depend on *which* groups those 8 thirds come from. FIFA
publishes an official allocation table with one row per combination of qualifying-third
groups (C(12,8) = 495 rows). We DO NOT invent that table: it is loaded from
``data/seed/r32_bracket_map.json`` when present.

Qualification-to-R32 probabilities — the required deliverable — do **not** need this table
(they only need the third-place ranking in ``tiebreakers.py``). The bracket mapping is the
seam for the optional knockout extension (prompt §7 stretch). Until the official table is
supplied, :func:`assign_r32` raises a clear, actionable error rather than guessing.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..domain import GROUP_LABELS


class OfficialBracketUnavailable(NotImplementedError):
    """Raised when an R32 assignment is requested but the official table is absent."""


def load_bracket_map(seed_dir: Path) -> dict | None:
    """Load the official R32 allocation table if it has been supplied, else ``None``."""
    path = seed_dir / "r32_bracket_map.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_r32_ties(seed_dir: Path) -> list[dict] | None:
    """Load the verified fixed R32 ties (winners/runners-up + third-place eligibility pools).

    Returns the 16 ties from ``data/seed/r32_bracket.json`` (each with match number, date,
    venue, and slot tokens like ``1A``/``2B``/``3rd:A/B/C/D/F``). This is the confirmed
    bracket *structure*; resolving the eight ``3rd:`` slots to concrete groups requires the
    full FIFA Annex C allocation table (see :func:`assign_r32`). Used for UI display and as
    the knockout-extension hook.
    """
    path = seed_dir / "r32_bracket.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)["ties"]


def assign_r32(
    group_winners: dict[str, str],
    group_runners: dict[str, str],
    best_thirds_groups: list[str],
    bracket_map: dict | None,
) -> list[tuple[str, str]]:
    """Return the 16 R32 ties as (teamA, teamB) descriptors.

    ``best_thirds_groups`` is the *sorted* list of the 8 group letters whose third-placed
    teams qualified. ``bracket_map`` keys those combinations (e.g. "ABCDEFGH") to the slot
    assignment for thirds. Raises :class:`OfficialBracketUnavailable` if the table is missing
    — callers that only need qualification probabilities never reach here.
    """
    if bracket_map is None:
        raise OfficialBracketUnavailable(
            "Official FIFA R32 allocation table not found at data/seed/r32_bracket_map.json. "
            "Qualification probabilities do not require it; supply the official table to "
            "enable the knockout-bracket extension."
        )
    key = "".join(sorted(best_thirds_groups))
    if key not in bracket_map.get("combinations", {}):
        raise OfficialBracketUnavailable(
            f"Third-place combination {key!r} not present in supplied bracket table."
        )
    # Table-driven assignment; structure validated by tests once a real table is supplied.
    assignment = bracket_map["combinations"][key]  # e.g. {"1A": "3B", ...}
    ties: list[tuple[str, str]] = []
    for slot in bracket_map["fixed_slots"]:
        a = _resolve_slot(slot["a"], group_winners, group_runners, assignment)
        b = _resolve_slot(slot["b"], group_winners, group_runners, assignment)
        ties.append((a, b))
    return ties


def _resolve_slot(token: str, winners: dict[str, str], runners: dict[str, str], thirds) -> str:
    """Resolve a slot token like '1A' (winner of A), '2C' (runner-up C), '3X' (a third)."""
    if token.startswith("3"):
        token = thirds.get(token, token)  # remap third-slot to a concrete group
    pos, grp = token[0], token[1]
    assert grp in GROUP_LABELS, f"bad group in slot token: {token}"
    return winners[grp] if pos == "1" else runners[grp]
