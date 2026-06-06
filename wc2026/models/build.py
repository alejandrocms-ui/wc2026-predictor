"""Construct a ready-to-predict Dixon-Coles model from data + Elo, with cold-start fill.

Several 2026 teams have few recent comparable matches. We fit the Dixon-Coles model on the
recent historical window, then **fill any missing or low-data team** with attack/defense
derived from its Elo rating. This is the pragmatic stand-in for the (flagged-for-later)
Bayesian partial-pooling model: it prevents undefined/overconfident parameters for low-data
sides while keeping the principled fit where data is plentiful.
"""

from __future__ import annotations

import pandas as pd

from .dixon_coles import DixonColesModel


def build_dixon_coles(
    results: pd.DataFrame,
    elo: dict[str, float],
    *,
    fit_years: int = 10,
    halflife_days: float = 547.0,
    teams_of_interest: list[str] | None = None,
) -> DixonColesModel:
    """Fit Dixon-Coles on the recent window, then Elo-fill cold-start teams."""
    elo_model = DixonColesModel.from_elo(elo)

    df = results.copy()
    if not df.empty and fit_years:
        cutoff = df["date"].max() - pd.Timedelta(days=365 * fit_years)
        df = df[df["date"] >= cutoff]

    # Start the optimiser from the Elo prior so fitted params are well-initialised.
    model = DixonColesModel(
        attack=dict(elo_model.attack),
        defense=dict(elo_model.defense),
        home_adv=elo_model.home_adv,
        rho=elo_model.rho,
        base_log=elo_model.base_log,
    )
    if not df.empty:
        model.fit(df, halflife_days=halflife_days)

    # Cold-start fill: any team of interest absent from the fit gets its Elo-derived params.
    interest = teams_of_interest or list(elo)
    for t in interest:
        if t not in model.attack and t in elo_model.attack:
            model.attack[t] = elo_model.attack[t]
            model.defense[t] = elo_model.defense[t]
    return model
