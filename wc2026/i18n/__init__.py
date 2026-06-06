"""Minimal i18n layer. All UI strings are keyed so the language is switchable.

Default language is Spanish (neutral) per project config; English is fully available.
Usage::

    from wc2026.i18n import Translator
    t = Translator("es")
    t("app_title")            # -> "Predictor Copa Mundial 2026"
    t("greeting", name="X")   # supports str.format kwargs
"""

from __future__ import annotations

LANGUAGES = ("es", "en")
DEFAULT_LANG = "es"

STRINGS: dict[str, dict[str, str]] = {
    # ── App chrome ──────────────────────────────────────────────────────────
    "app_title": {
        "es": "Predictor Copa Mundial 2026 ⚽",
        "en": "2026 World Cup Predictor ⚽",
    },
    "hero_title": {
        "es": "Predictor Copa Mundial 2026",
        "en": "2026 World Cup Predictor",
    },
    "hero_chip": {
        "es": "Basado en {n:,} simulaciones Monte Carlo · ensamble calibrado",
        "en": "Based on {n:,} Monte Carlo simulations · calibrated ensemble",
    },
    "app_subtitle": {
        "es": "Probabilidades calibradas para la fase de grupos y la clasificación a Dieciseisavos (R32).",
        "en": "Calibrated probabilities for the group stage and Round-of-32 qualification.",
    },
    "nav_match": {"es": "Predictor de partido", "en": "Match predictor"},
    "nav_group": {"es": "Explorador de grupos", "en": "Group explorer"},
    "nav_dashboard": {"es": "Panel del torneo", "en": "Tournament dashboard"},
    "nav_methodology": {"es": "Metodología y modelo", "en": "Methodology & model card"},
    "language": {"es": "Idioma", "en": "Language"},
    "page": {"es": "Página", "en": "Page"},
    # ── Data tier badge ─────────────────────────────────────────────────────
    "data_tier": {"es": "Nivel de datos", "en": "Data tier"},
    "tier0_label": {"es": "Nivel 0 (gratis, sin claves)", "en": "Tier 0 (free, no keys)"},
    "tier1_label": {"es": "Nivel 1 (APIs gratuitas)", "en": "Tier 1 (free APIs)"},
    "tier2_label": {"es": "Nivel 2 (datos de pago)", "en": "Tier 2 (paid data)"},
    "seed_label": {"es": "Semilla (muestra incluida)", "en": "Seed (bundled sample)"},
    # ── Match page ──────────────────────────────────────────────────────────
    "select_home": {"es": "Equipo local", "en": "Home team"},
    "select_away": {"es": "Equipo visitante", "en": "Away team"},
    "neutral_venue": {"es": "Sede neutral", "en": "Neutral venue"},
    "predict": {"es": "Predecir", "en": "Predict"},
    "scoreline_heatmap": {"es": "Mapa de calor de marcadores", "en": "Scoreline heatmap"},
    "home_goals": {"es": "Goles local", "en": "Home goals"},
    "away_goals": {"es": "Goles visitante", "en": "Away goals"},
    "market_1x2": {"es": "1X2 (Local / Empate / Visitante)", "en": "1X2 (Home / Draw / Away)"},
    "home_win": {"es": "Gana local", "en": "Home win"},
    "draw": {"es": "Empate", "en": "Draw"},
    "away_win": {"es": "Gana visitante", "en": "Away win"},
    "btts": {"es": "Ambos marcan", "en": "Both teams to score"},
    "over_25": {"es": "Más de 2.5 goles", "en": "Over 2.5 goals"},
    "under_25": {"es": "Menos de 2.5 goles", "en": "Under 2.5 goals"},
    "most_likely_scores": {"es": "Marcadores más probables", "en": "Most likely scores"},
    "expected_goals": {"es": "Goles esperados", "en": "Expected goals"},
    "score": {"es": "Marcador", "en": "Score"},
    "probability": {"es": "Probabilidad", "en": "Probability"},
    # ── Group / dashboard ───────────────────────────────────────────────────
    "group": {"es": "Grupo", "en": "Group"},
    "team": {"es": "Equipo", "en": "Team"},
    "select_group": {"es": "Selecciona un grupo", "en": "Select a group"},
    "p_win_group": {"es": "Gana grupo", "en": "Win group"},
    "p_top2": {"es": "Top 2", "en": "Top 2"},
    "p_best_third": {"es": "Mejor 3º", "en": "Best third"},
    "p_reach_r32": {"es": "Llega a R32", "en": "Reach R32"},
    "exp_points": {"es": "Puntos esp.", "en": "Exp. points"},
    "exp_gd": {"es": "Dif. gol esp.", "en": "Exp. GD"},
    "finishing_distribution": {"es": "Distribución de posición", "en": "Finishing distribution"},
    "qualification_probs": {"es": "Probabilidades de clasificación", "en": "Qualification probabilities"},
    "expected_table": {"es": "Tabla esperada", "en": "Expected table"},
    "who_tops_groups": {
        "es": "Quién encabeza su grupo / se cuela como mejor tercero",
        "en": "Who tops their group / sneaks in as best third",
    },
    "pos_1": {"es": "1º", "en": "1st"},
    "pos_2": {"es": "2º", "en": "2nd"},
    "pos_3": {"es": "3º", "en": "3rd"},
    "pos_4": {"es": "4º", "en": "4th"},
    # ── Methodology / responsible use ───────────────────────────────────────
    "methodology_title": {"es": "Metodología", "en": "Methodology"},
    "limitations_title": {"es": "Limitaciones y uso responsable", "en": "Limitations & responsible use"},
    "not_betting": {
        "es": "⚠️ Herramienta analítica y educativa. La incertidumbre es irreducible; "
        "no es asesoramiento de apuestas. Las predicciones son más débiles para "
        "selecciones con pocos datos recientes.",
        "en": "⚠️ Analytical and educational tool. Uncertainty is irreducible; this is not "
        "betting advice. Predictions are weaker for teams with little recent data.",
    },
    "no_predictions_yet": {
        "es": "No hay predicciones todavía. Ejecuta: python -m wc2026.pipeline",
        "en": "No predictions yet. Run: python -m wc2026.pipeline",
    },
    "model_primary": {
        "es": "Modelo primario: Dixon-Coles (Poisson bivariado) con decaimiento temporal.",
        "en": "Primary model: Dixon-Coles (bivariate Poisson) with time decay.",
    },
    "based_on_sims": {"es": "Basado en {n:,} simulaciones", "en": "Based on {n:,} simulations"},
    "r32_bracket": {"es": "Estructura del cuadro de Dieciseisavos (R32)", "en": "Round-of-32 bracket structure"},
    "r32_note": {
        "es": "Cruces fijos de ganadores/segundos confirmados; los 8 mejores terceros se asignan "
        "según la tabla oficial (Anexo C). 3º:X/Y = tercero de uno de esos grupos.",
        "en": "Fixed winner/runner-up ties confirmed; the 8 best thirds are assigned by the "
        "official table (Annex C). 3rd:X/Y = third from one of those groups.",
    },
    "match_no": {"es": "Partido", "en": "Match"},
    "venue": {"es": "Sede", "en": "Venue"},
    "date": {"es": "Fecha", "en": "Date"},
}


class Translator:
    def __init__(self, lang: str = DEFAULT_LANG):
        self.lang = lang if lang in LANGUAGES else DEFAULT_LANG

    def __call__(self, key: str, **kwargs) -> str:
        entry = STRINGS.get(key)
        if entry is None:
            return key  # surface the missing key rather than crashing
        text = entry.get(self.lang) or entry.get(DEFAULT_LANG) or key
        return text.format(**kwargs) if kwargs else text


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    return Translator(lang)(key, **kwargs)
