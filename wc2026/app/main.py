"""wc2026-predictor Streamlit app. Run with: streamlit run wc2026/app/main.py"""

from __future__ import annotations

# Make the repo root importable when run as a script (e.g. Streamlit Community Cloud, which
# does not `pip install` the package). This puts the directory that CONTAINS the ``wc2026``
# package on sys.path, so ``import wc2026...`` resolves and config's REPO_ROOT (and thus the
# data/ paths) still point at the repo working dir.
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from wc2026.app import theme  # noqa: E402
from wc2026.app.data import (  # noqa: E402
    get_model,
    get_spec,
    load_provenance_df,
    load_simulation_df,
)
from wc2026.config import get_settings  # noqa: E402
from wc2026.domain import MatchContext  # noqa: E402
from wc2026.i18n import LANGUAGES, Translator  # noqa: E402

st.set_page_config(page_title="Predictor Copa Mundial 2026 ⚽", page_icon="⚽", layout="wide")
st.markdown(theme.CSS, unsafe_allow_html=True)

_TIER_KEY = {"tier0": "tier0_label", "tier1": "tier1_label", "tier2": "tier2_label", "seed": "seed_label"}


def _sidebar() -> tuple[Translator, str]:
    settings = get_settings()
    default_idx = LANGUAGES.index(settings.lang) if settings.lang in LANGUAGES else 0
    lang = st.sidebar.selectbox("🌐 Idioma / Language", LANGUAGES, index=default_idx,
                                format_func=lambda x: {"es": "Español", "en": "English"}[x])
    t = Translator(lang)
    st.sidebar.title(t("app_title"))
    page = st.sidebar.radio(
        t("page"),
        ["nav_match", "nav_group", "nav_dashboard", "nav_methodology"],
        format_func=t,
    )
    return t, page


def _tier_badge(t: Translator, tier: str) -> None:
    label = t(_TIER_KEY.get(tier, "tier0_label"))
    color = {"tier0": "🟢", "tier1": "🔵", "tier2": "🟣", "seed": "🟡"}.get(tier, "🟢")
    st.caption(f"{color} **{t('data_tier')}:** {label}")


# ── Page: Match predictor ───────────────────────────────────────────────────
def page_match(t: Translator) -> None:
    st.header(t("nav_match"))
    spec = get_spec()
    teams = sorted(spec.teams)
    c1, c2, c3 = st.columns([3, 3, 2])
    home = c1.selectbox(t("select_home"), teams, index=teams.index("Brazil"),
                        format_func=theme.with_flag)
    away = c2.selectbox(t("select_away"), teams, index=teams.index("Spain"),
                        format_func=theme.with_flag)
    neutral = c3.checkbox(t("neutral_venue"), value=True)
    if home == away:
        st.warning("⚠️ " + t("select_home") + " ≠ " + t("select_away"))
        return

    model, tier = get_model()
    sm = model.predict_match(home, away, MatchContext(neutral=neutral, data_tier=tier))
    _tier_badge(t, tier)

    h, d, a = sm.one_x_two
    m1, m2, m3 = st.columns(3)
    m1.metric(f"🏠 {theme.with_flag(home)}", f"{h*100:.1f}%", help=t("home_win"))
    m2.metric(f"🤝 {t('draw')}", f"{d*100:.1f}%")
    m3.metric(f"✈️ {theme.with_flag(away)}", f"{a*100:.1f}%", help=t("away_win"))

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(t("btts"), f"{sm.prob_btts*100:.1f}%")
    k2.metric(t("over_25"), f"{sm.prob_over(2.5)*100:.1f}%")
    k3.metric(t("under_25"), f"{sm.prob_under(2.5)*100:.1f}%")
    k4.metric(t("expected_goals"), f"{sm.expected_home_goals:.2f} – {sm.expected_away_goals:.2f}")

    left, right = st.columns([3, 2])
    with left:
        st.subheader(t("scoreline_heatmap"))
        n = min(6, sm.matrix.shape[0])
        sub = sm.matrix[:n, :n]
        vmax = float(sub.max())
        df = pd.DataFrame(
            [(i, j, round(float(sub[i, j]), 4)) for i in range(n) for j in range(n)],
            columns=["hg", "ag", "p"],
        )
        chart = (
            alt.Chart(df)
            .mark_rect()
            .encode(
                x=alt.X("ag:O", title=f"{t('away_goals')} ({away})"),
                y=alt.Y("hg:O", title=f"{t('home_goals')} ({home})", sort="descending"),
                color=alt.Color(
                    "p:Q",
                    title=t("probability"),
                    scale=alt.Scale(scheme="blues", domain=[0.0, vmax]),
                ),
                tooltip=[alt.Tooltip("hg:O"), alt.Tooltip("ag:O"), alt.Tooltip("p:Q", format=".1%")],
            )
            .properties(height=340)
        )
        text = chart.mark_text(baseline="middle").encode(
            text=alt.Text("p:Q", format=".0%"),
            color=alt.condition(f"datum.p > {vmax * 0.5}", alt.value("white"), alt.value("black")),
        )
        st.altair_chart(chart + text, use_container_width=True)
    with right:
        st.subheader(t("most_likely_scores"))
        top = sm.most_likely_scores(7)
        st.dataframe(
            pd.DataFrame(
                {t("score"): [f"{i}-{j}" for i, j, _ in top],
                 t("probability"): [f"{p*100:.1f}%" for *_, p in top]}
            ),
            hide_index=True,
            use_container_width=True,
        )
    st.info(t("not_betting"))


# ── Page: Group explorer ────────────────────────────────────────────────────
def page_group(t: Translator) -> None:
    st.header(t("nav_group"))
    spec = get_spec()
    sim = load_simulation_df()
    if sim.empty:
        st.warning(t("no_predictions_yet"))
        return
    label = st.selectbox(t("select_group"), sorted(spec.groups))
    g = sim[sim["group"] == label].copy()
    g = g.sort_values(["p_reach_r32", "p_win_group", "exp_points"], ascending=False)
    g["team_flag"] = g["team"].map(theme.with_flag)

    st.markdown(
        f"### {theme.group_badge(label)}&nbsp; {t('group')} {label} — {t('qualification_probs')}",
        unsafe_allow_html=True,
    )
    show = pd.DataFrame(
        {
            t("team"): g["team_flag"],
            t("p_win_group"): (g["p_win_group"] * 100).round(1),
            t("p_top2"): (g["p_top2"] * 100).round(1),
            t("p_best_third"): (g["p_best_third"] * 100).round(1),
            t("p_reach_r32"): (g["p_reach_r32"] * 100).round(1),
            t("exp_points"): g["exp_points"].round(2),
            t("exp_gd"): g["exp_gd"].round(2),
        }
    )
    st.dataframe(
        show,
        hide_index=True,
        use_container_width=True,
        column_config={
            t("p_reach_r32"): st.column_config.ProgressColumn(
                t("p_reach_r32"), min_value=0, max_value=100, format="%.1f%%"
            ),
        },
    )

    st.subheader(t("finishing_distribution"))
    fd = g.melt(
        id_vars="team_flag",
        value_vars=["p_finish_1", "p_finish_2", "p_finish_3", "p_finish_4"],
        var_name="pos", value_name="p",
    )
    posmap = {"p_finish_1": t("pos_1"), "p_finish_2": t("pos_2"),
              "p_finish_3": t("pos_3"), "p_finish_4": t("pos_4")}
    fd["pos"] = fd["pos"].map(posmap)
    fd["p"] = fd["p"].round(4)
    # Green→amber→red→grey: qualify (1st/2nd) vs out (3rd/4th).
    pos_order = [t("pos_1"), t("pos_2"), t("pos_3"), t("pos_4")]
    chart = (
        alt.Chart(fd)
        .mark_bar()
        .encode(
            x=alt.X("p:Q", stack="normalize", title=t("probability"), axis=alt.Axis(format="%")),
            y=alt.Y("team_flag:N", title=t("team"), sort=list(g["team_flag"])),
            color=alt.Color(
                "pos:N", title="", sort=pos_order,
                scale=alt.Scale(domain=pos_order, range=["#00843D", "#7FC97F", "#FFB81C", "#E4002B"]),
            ),
            order=alt.Order("pos:N"),
            tooltip=["team_flag", "pos", alt.Tooltip("p:Q", format=".1%")],
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)
    st.info(t("not_betting"))


# ── Page: Tournament dashboard ──────────────────────────────────────────────
def page_dashboard(t: Translator) -> None:
    st.header(t("nav_dashboard"))
    sim = load_simulation_df()
    if sim.empty:
        st.warning(t("no_predictions_yet"))
        return
    st.caption(t("who_tops_groups"))
    df = sim.copy().sort_values("p_reach_r32", ascending=False)
    show = pd.DataFrame(
        {
            t("team"): df["team"].map(theme.with_flag),
            t("group"): df["group"],
            t("p_win_group"): (df["p_win_group"] * 100).round(1),
            t("p_top2"): (df["p_top2"] * 100).round(1),
            t("p_best_third"): (df["p_best_third"] * 100).round(1),
            t("p_reach_r32"): (df["p_reach_r32"] * 100).round(1),
            t("exp_points"): df["exp_points"].round(2),
        }
    )
    st.dataframe(
        show,
        hide_index=True,
        use_container_width=True,
        height=560,
        column_config={
            t("p_reach_r32"): st.column_config.ProgressColumn(
                t("p_reach_r32"), min_value=0, max_value=100, format="%.1f%%"
            ),
        },
    )


# ── Page: Methodology / model card ──────────────────────────────────────────
def page_methodology(t: Translator) -> None:
    st.header(t("nav_methodology"))
    sim = load_simulation_df()
    n = int(sim["n_sims"].iloc[0]) if not sim.empty else 0
    st.write(t("model_primary"))
    if n:
        st.caption(t("based_on_sims", n=n))

    prov = load_provenance_df()
    if not prov.empty:
        st.subheader(t("data_tier"))
        st.dataframe(prov, hide_index=True, use_container_width=True)

    # Surface the model report if the backtest produced one.
    settings = get_settings()
    report = settings.data_dir.parent / "MODEL_REPORT.md"
    if report.exists():
        with st.expander("MODEL_REPORT.md", expanded=False):
            st.markdown(report.read_text(encoding="utf-8"))

    # Official R32 bracket structure (winners/runners-up fixed; thirds via Annex C table).
    from wc2026.sim.bracket import load_r32_ties

    ties = load_r32_ties(settings.seed_dir)
    if ties:
        with st.expander(t("r32_bracket"), expanded=False):
            st.caption(t("r32_note"))
            st.dataframe(
                pd.DataFrame(
                    {
                        t("match_no"): [ti["match_no"] for ti in ties],
                        t("date"): [ti["date"] for ti in ties],
                        "A": [ti["a"] for ti in ties],
                        "B": [ti["b"] for ti in ties],
                        t("venue"): [ti["venue_city"] for ti in ties],
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )

    st.subheader(t("limitations_title"))
    st.warning(t("not_betting"))


def main() -> None:
    t, page = _sidebar()
    sim = load_simulation_df()
    n = int(sim["n_sims"].iloc[0]) if not sim.empty else 0
    chip = t("hero_chip", n=n) if n else t("model_primary")
    st.markdown(
        theme.hero_html(t("hero_title"), t("app_subtitle"), chip),
        unsafe_allow_html=True,
    )
    {
        "nav_match": page_match,
        "nav_group": page_group,
        "nav_dashboard": page_dashboard,
        "nav_methodology": page_methodology,
    }[page](t)
    st.markdown(theme.FOOTER_HTML, unsafe_allow_html=True)


main()
