"""End-to-end Monte Carlo accounting and reproducibility tests."""

from __future__ import annotations

from wc2026.domain import GROUP_LABELS
from wc2026.engine import run_tournament_simulation
from wc2026.models.dixon_coles import DixonColesModel
from wc2026.tournament import load_spec


def _model(spec):
    elo = {name: t.elo_seed for name, t in spec.teams.items()}
    return DixonColesModel.from_elo(elo)


def test_simulation_probability_accounting():
    spec = load_spec()
    model = _model(spec)
    _, res = run_tournament_simulation(spec, model, n_sims=3000, seed=123)

    # Every team has a full finishing distribution summing to 1.
    for t in res.teams.values():
        assert abs(sum(t.finish_dist) - 1.0) < 1e-9

    # Exactly 2 teams qualify top-2 per group => sum of p_top2 in a group == 2.
    for label in GROUP_LABELS:
        s = sum(res.teams[t].p_top2 for t in spec.groups[label])
        assert abs(s - 2.0) < 1e-9, (label, s)

    # Exactly 8 best-third slots across the whole tournament.
    total_best_third = sum(t.p_best_third for t in res.teams.values())
    assert abs(total_best_third - 8.0) < 1e-6

    # Exactly 32 teams reach the Round of 32 (24 top-2 + 8 thirds).
    total_r32 = sum(t.p_reach_r32 for t in res.teams.values())
    assert abs(total_r32 - 32.0) < 1e-6

    # Each group: exactly one winner and one runner-up in expectation.
    for label in GROUP_LABELS:
        assert abs(sum(res.teams[t].p_win_group for t in spec.groups[label]) - 1.0) < 1e-9
        assert abs(sum(res.teams[t].p_runner_up for t in spec.groups[label]) - 1.0) < 1e-9


def test_simulation_is_reproducible():
    spec = load_spec()
    model = _model(spec)
    _, a = run_tournament_simulation(spec, model, n_sims=1500, seed=777)
    _, b = run_tournament_simulation(spec, model, n_sims=1500, seed=777)
    for t in spec.teams:
        assert a.teams[t].p_reach_r32 == b.teams[t].p_reach_r32


def test_stronger_teams_more_likely_to_advance():
    spec = load_spec()
    model = _model(spec)
    _, res = run_tournament_simulation(spec, model, n_sims=4000, seed=9)
    # Argentina (high seed Elo) should be heavily favoured to advance from its group.
    assert res.teams["Argentina"].p_reach_r32 > 0.7
    # A low-Elo side should be a clear underdog.
    assert res.teams["Haiti"].p_reach_r32 < 0.5
