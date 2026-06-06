"""Dixon-Coles bivariate-Poisson model — the primary scoreline model.

Two cooperating paths share one ``predict_match`` contract:

* **Fitted** — :meth:`DixonColesModel.fit` estimates per-team attack/defense parameters,
  a home-advantage term and the Dixon-Coles low-score correlation correction ``rho`` by
  maximum likelihood with exponential time-decay weighting, from a frame of historical
  international results. This is the statistically principled path used once Tier-0 data
  is ingested.
* **Elo prior** — :meth:`DixonColesModel.from_elo` derives attack/defense parameters
  analytically from Elo ratings so the app produces sensible, calibrated-ish predictions
  **with zero data** (the seed Elo ships in the repo). Cold-start teams and the offline
  path both rely on this.

Both produce a full ``P(home=i, away=j)`` matrix with the Dixon-Coles ``tau`` correction
applied to the 0-0 / 1-0 / 0-1 / 1-1 cells, which a plain double-Poisson mis-prices.

The Dixon & Coles (1997) low-score adjustment:
    tau(0,0) = 1 - lh*la*rho
    tau(0,1) = 1 + lh*rho
    tau(1,0) = 1 + la*rho
    tau(1,1) = 1 - rho
    tau(i,j) = 1 otherwise
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import poisson

from ..domain import MatchContext
from .scoreline import ScorelineMatrix

# Default Elo-prior calibration constants (documented; tunable via backtest).
# log goal-rate at parity ~ log(1.30) gives ~2.6 total goals (intl average).
_ELO_BASE_LOG = float(np.log(1.30))
# Each Elo point shifts the log goal supremacy by this much. 0.0020/pt => a 200-Elo edge
# is ~0.40 in log space (home/away rate ratio ~1.5), broadly matching observed supremacy.
_ELO_SLOPE = 0.0020
# Home advantage as an additive log-rate term (~exp(0.30)=1.35x) when not neutral.
_DEFAULT_HOME_ADV = 0.30
# Default low-score correlation; mildly negative is typical for internationals.
_DEFAULT_RHO = -0.05
_MAX_GOALS = 10


def _tau(i: np.ndarray, j: np.ndarray, lh: float, la: float, rho: float) -> np.ndarray:
    """Vectorised Dixon-Coles correction over a grid of (i, j)."""
    out = np.ones_like(i, dtype=float)
    out[(i == 0) & (j == 0)] = 1.0 - lh * la * rho
    out[(i == 0) & (j == 1)] = 1.0 + lh * rho
    out[(i == 1) & (j == 0)] = 1.0 + la * rho
    out[(i == 1) & (j == 1)] = 1.0 - rho
    return out


@dataclass(slots=True)
class DixonColesModel:
    attack: dict[str, float] = field(default_factory=dict)
    defense: dict[str, float] = field(default_factory=dict)
    home_adv: float = _DEFAULT_HOME_ADV
    rho: float = _DEFAULT_RHO
    base_log: float = _ELO_BASE_LOG  # global log goal level (mu_att - mu_def + c)
    max_goals: int = _MAX_GOALS
    # Retained for cold-start: teams unseen in attack/defense fall back to these.
    default_attack: float = 0.0
    default_defense: float = 0.0

    # ── Construction from Elo (zero-data path) ──────────────────────────────
    @classmethod
    def from_elo(
        cls,
        elo: dict[str, float],
        *,
        home_adv: float = _DEFAULT_HOME_ADV,
        rho: float = _DEFAULT_RHO,
        slope: float = _ELO_SLOPE,
        base_log: float = _ELO_BASE_LOG,
    ) -> DixonColesModel:
        """Derive attack/defense params from Elo so predict works with no fit data.

        With ``r = slope * (elo - mean_elo)`` we set ``attack = +r`` and ``defense = +r``
        (defensive *strength*). Then ``lambda_home = exp(base + home_adv + att_h - def_a)``
        rises with the home team's rating and falls with the away team's, and vice-versa.
        """
        if not elo:
            return cls(home_adv=home_adv, rho=rho, base_log=base_log)
        mean_elo = float(np.mean(list(elo.values())))
        attack = {t: slope * (e - mean_elo) for t, e in elo.items()}
        defense = dict(attack)  # symmetric: a strong team both scores more and concedes less
        return cls(
            attack=attack,
            defense=defense,
            home_adv=home_adv,
            rho=rho,
            base_log=base_log,
        )

    # ── Core: expected goals ────────────────────────────────────────────────
    def expected_goals(
        self, home: str, away: str, context: MatchContext | None = None
    ) -> tuple[float, float]:
        ctx = context or MatchContext()
        ah = self.attack.get(home, self.default_attack)
        aa = self.attack.get(away, self.default_attack)
        dh = self.defense.get(home, self.default_defense)
        da = self.defense.get(away, self.default_defense)
        home_field = 0.0 if ctx.neutral else self.home_adv
        log_lh = self.base_log + home_field + ah - da + ctx.home_logit_adj
        log_la = self.base_log + aa - dh + ctx.away_logit_adj
        # Clamp to a sane goal-rate range to keep the Poisson tail well-behaved.
        lh = float(np.clip(np.exp(log_lh), 0.05, 8.0))
        la = float(np.clip(np.exp(log_la), 0.05, 8.0))
        return lh, la

    # ── Core: scoreline matrix ──────────────────────────────────────────────
    def predict_match(
        self, home: str, away: str, context: MatchContext | None = None
    ) -> ScorelineMatrix:
        ctx = context or MatchContext()
        lh, la = self.expected_goals(home, away, ctx)
        n = self.max_goals + 1
        gh = poisson.pmf(np.arange(n), lh)
        ga = poisson.pmf(np.arange(n), la)
        mat = np.outer(gh, ga)  # independent Poisson baseline
        i = np.arange(n)[:, None] * np.ones((1, n), dtype=int)
        j = np.ones((n, 1), dtype=int) * np.arange(n)[None, :]
        mat = mat * _tau(i, j, lh, la, self.rho)
        mat = np.clip(mat, 0.0, None)  # tau can push a cell slightly negative
        return ScorelineMatrix(matrix=mat, home=home, away=away, data_tier=ctx.data_tier)

    # ── Fitting by weighted maximum likelihood ──────────────────────────────
    def fit(
        self,
        results,
        *,
        halflife_days: float = 547.0,
        as_of: str | None = None,
        ridge: float = 1e-3,
        max_iter: int = 200,
    ) -> DixonColesModel:
        """Fit attack/defense/home_adv/rho by time-decay-weighted MLE.

        ``results`` is a pandas DataFrame with columns
        ``[date, home, away, home_score, away_score, neutral]``. Weights decay
        exponentially with match age relative to ``as_of`` (default: latest date).
        Falls back gracefully — if SciPy optimisation fails, the pre-fit (Elo) params
        are retained so the app never crashes.
        """
        import pandas as pd
        from scipy.optimize import minimize

        df = results.dropna(subset=["home", "away", "home_score", "away_score"]).copy()
        if df.empty:
            return self
        df["date"] = pd.to_datetime(df["date"])
        ref = pd.to_datetime(as_of) if as_of else df["date"].max()
        age_days = (ref - df["date"]).dt.days.clip(lower=0).to_numpy()
        weights = 0.5 ** (age_days / float(halflife_days))

        teams = sorted(set(df["home"]) | set(df["away"]))
        idx = {t: k for k, t in enumerate(teams)}
        nt = len(teams)
        hg = df["home_score"].to_numpy(dtype=float)
        ag = df["away_score"].to_numpy(dtype=float)
        hi = df["home"].map(idx).to_numpy()
        ai = df["away"].map(idx).to_numpy()
        neutral = (
            df["neutral"].fillna(False).to_numpy(dtype=bool)
            if "neutral" in df
            else np.zeros(len(df), dtype=bool)
        )

        # Param vector: [attack(nt), defense(nt), home_adv, rho, base_log].
        # Identifiability: pin mean attack and mean defense to 0 via ridge + recentring.
        def unpack(x):
            att = x[:nt]
            dfn = x[nt : 2 * nt]
            ha, rho, base = x[2 * nt], x[2 * nt + 1], x[2 * nt + 2]
            return att, dfn, ha, rho, base

        def nll(x):
            att, dfn, ha, rho, base = unpack(x)
            rho = np.clip(rho, -0.2, 0.2)
            lh = np.exp(base + np.where(neutral, 0.0, ha) + att[hi] - dfn[ai])
            la = np.exp(base + att[ai] - dfn[hi])
            lh = np.clip(lh, 1e-3, 12.0)
            la = np.clip(la, 1e-3, 12.0)
            # Poisson log-lik (drop constant log(k!) — irrelevant to the argmin).
            ll = hg * np.log(lh) - lh + ag * np.log(la) - la
            # Dixon-Coles correction only affects the four low-score cells.
            corr = np.ones(len(df))
            m00 = (hg == 0) & (ag == 0)
            m01 = (hg == 0) & (ag == 1)
            m10 = (hg == 1) & (ag == 0)
            m11 = (hg == 1) & (ag == 1)
            corr[m00] = 1.0 - lh[m00] * la[m00] * rho
            corr[m01] = 1.0 + lh[m01] * rho
            corr[m10] = 1.0 + la[m10] * rho
            corr[m11] = 1.0 - rho
            corr = np.clip(corr, 1e-6, None)
            ll = ll + np.log(corr)
            penalty = ridge * (np.sum(att**2) + np.sum(dfn**2))
            return -np.sum(weights * ll) + penalty

        x0 = np.concatenate(
            [
                np.array([self.attack.get(t, 0.0) for t in teams]),
                np.array([self.defense.get(t, 0.0) for t in teams]),
                [self.home_adv, self.rho, self.base_log],
            ]
        )
        try:
            res = minimize(nll, x0, method="L-BFGS-B", options={"maxiter": max_iter})
            att, dfn, ha, rho, base = unpack(res.x)
            # Recentre for identifiability (mean 0 attack & defense; level absorbed in base).
            base = base + att.mean() - dfn.mean()
            att = att - att.mean()
            dfn = dfn - dfn.mean()
            self.attack = {t: float(att[idx[t]]) for t in teams}
            self.defense = {t: float(dfn[idx[t]]) for t in teams}
            self.home_adv = float(ha)
            self.rho = float(np.clip(rho, -0.2, 0.2))
            self.base_log = float(base)
        except Exception:  # pragma: no cover - defensive; keep prior params
            return self
        return self
