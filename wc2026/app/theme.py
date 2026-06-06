"""Visual theme for the Streamlit app — original World-Cup-2026-flavoured styling.

IMPORTANT (intellectual property): this uses ONLY original, generic football motifs (a ⚽
emoji/CSS ball, host-nation flag emojis, a festive multicolour palette). It deliberately does
**not** reproduce FIFA's trademarked 2026 mascots (Maple/Zayu/Clutch) or the official match
ball, to avoid any IP issues while still feeling like a World Cup app.
"""

from __future__ import annotations

# Flag emojis for the 48 teams (display only). Falls back to a generic ⚽ if missing.
TEAM_FLAGS: dict[str, str] = {
    "Mexico": "🇲🇽", "South Africa": "🇿🇦", "Korea Republic": "🇰🇷", "Czechia": "🇨🇿",
    "Canada": "🇨🇦", "Switzerland": "🇨🇭", "Qatar": "🇶🇦", "Bosnia and Herzegovina": "🇧🇦",
    "Brazil": "🇧🇷", "Morocco": "🇲🇦", "Haiti": "🇭🇹", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "United States": "🇺🇸", "Paraguay": "🇵🇾", "Australia": "🇦🇺", "Türkiye": "🇹🇷",
    "Germany": "🇩🇪", "Curaçao": "🇨🇼", "Côte d'Ivoire": "🇨🇮", "Ecuador": "🇪🇨",
    "Netherlands": "🇳🇱", "Japan": "🇯🇵", "Tunisia": "🇹🇳", "Sweden": "🇸🇪",
    "Belgium": "🇧🇪", "Egypt": "🇪🇬", "Iran": "🇮🇷", "New Zealand": "🇳🇿",
    "Spain": "🇪🇸", "Cabo Verde": "🇨🇻", "Saudi Arabia": "🇸🇦", "Uruguay": "🇺🇾",
    "France": "🇫🇷", "Senegal": "🇸🇳", "Norway": "🇳🇴", "Iraq": "🇮🇶",
    "Argentina": "🇦🇷", "Algeria": "🇩🇿", "Austria": "🇦🇹", "Jordan": "🇯🇴",
    "Portugal": "🇵🇹", "Uzbekistan": "🇺🇿", "Colombia": "🇨🇴", "Congo DR": "🇨🇩",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Croatia": "🇭🇷", "Ghana": "🇬🇭", "Panama": "🇵🇦",
}


def flag(team: str) -> str:
    return TEAM_FLAGS.get(team, "⚽")


def with_flag(team: str) -> str:
    return f"{flag(team)} {team}"


# Per-group accent colours (A–L) for badges, cycling a vibrant festive palette.
GROUP_COLORS = {
    "A": "#E4002B", "B": "#0072CE", "C": "#00843D", "D": "#FFB81C",
    "E": "#7C2AA8", "F": "#FF6B00", "G": "#00B5C9", "H": "#D81B60",
    "I": "#1565C0", "J": "#2E7D32", "K": "#F9A825", "L": "#5E35B1",
}


def group_badge(label: str) -> str:
    color = GROUP_COLORS.get(label, "#444")
    return (
        f'<span style="background:{color};color:#fff;border-radius:8px;'
        f'padding:2px 10px;font-weight:700;font-size:0.85rem">{label}</span>'
    )


# ── Global CSS (Google fonts + festive theme) ───────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap');

:root {
  --wc-pink:   #E4007C;
  --wc-purple: #6A1B9A;
  --wc-blue:   #0072CE;
  --wc-teal:   #00B5C9;
  --wc-green:  #00843D;
  --wc-gold:   #FFC72C;
  --wc-ink:    #14142B;
}

/* Base typography */
html, body, [class*="css"], .stApp { font-family: 'Inter', system-ui, sans-serif; }
h1, h2, h3, h4 { font-family: 'Sora', 'Inter', sans-serif !important; letter-spacing: -0.02em; }

.stApp {
  background:
    radial-gradient(1200px 600px at 100% -10%, rgba(0,181,201,0.08), transparent 60%),
    radial-gradient(1000px 500px at -10% 0%, rgba(228,0,124,0.08), transparent 55%),
    #f7f8fc;
}

/* ── Hero banner ── */
.wc-hero {
  margin: -1rem -1rem 1.2rem -1rem;
  padding: 2.0rem 2.2rem 1.8rem 2.2rem;
  border-radius: 0 0 26px 26px;
  background: linear-gradient(115deg, var(--wc-purple) 0%, var(--wc-pink) 38%, var(--wc-blue) 72%, var(--wc-teal) 100%);
  color: #fff;
  box-shadow: 0 14px 40px rgba(106,27,154,0.30);
  position: relative;
  overflow: hidden;
}
.wc-hero::after {              /* subtle football-pattern dots */
  content:""; position:absolute; inset:0; opacity:0.10;
  background-image: radial-gradient(circle, #fff 1.4px, transparent 1.6px);
  background-size: 22px 22px;
  pointer-events:none;
}
.wc-hero h1 {
  margin:0; font-size: 2.45rem; font-weight: 800; color:#fff !important;
  display:flex; align-items:center; gap:.6rem; text-shadow:0 2px 10px rgba(0,0,0,.18);
}
.wc-ball { display:inline-block; animation: wc-spin 9s linear infinite; font-size:2.2rem; }
@keyframes wc-spin { to { transform: rotate(360deg); } }
.wc-hero p { margin:.5rem 0 0; font-size:1.02rem; opacity:.96; max-width: 70ch; }
.wc-hosts { margin-top:.7rem; font-size:1.4rem; letter-spacing:.15rem; }
.wc-chip {
  display:inline-block; margin-top:.8rem; padding:.28rem .8rem; border-radius:999px;
  background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.35);
  font-size:.82rem; font-weight:600; backdrop-filter: blur(4px);
}

/* ── Metric cards ── */
[data-testid="stMetric"] {
  background:#fff; border-radius:16px; padding:14px 16px 10px;
  box-shadow:0 4px 16px rgba(20,20,43,.06); border:1px solid #eef0f6;
  border-top:3px solid var(--wc-pink); transition:transform .12s ease, box-shadow .12s ease;
}
[data-testid="stMetric"]:hover { transform:translateY(-2px); box-shadow:0 10px 26px rgba(20,20,43,.10); }
[data-testid="stMetricValue"] { font-family:'Sora',sans-serif; font-weight:700; color:var(--wc-ink); }
[data-testid="stMetricLabel"] p { font-weight:600; color:#5b5f76; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #1b1340 0%, #2a1a5e 60%, #3a1d6e 100%);
}
[data-testid="stSidebar"] * { color:#ECE9FB !important; }
[data-testid="stSidebar"] h1 { color:#fff !important; font-size:1.15rem; }
[data-testid="stSidebar"] [role="radiogroup"] label {
  padding:.35rem .5rem; border-radius:10px; transition:background .12s ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background:rgba(255,255,255,.08); }

/* Section headings get a coloured accent bar */
.main h2 {
  border-left:5px solid var(--wc-pink); padding-left:.6rem; margin-top:.4rem;
}
.main h3 { color:var(--wc-purple); }

/* Dataframes */
[data-testid="stDataFrame"] { border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(20,20,43,.05); }

/* Disclaimer / info boxes */
[data-testid="stAlert"] { border-radius:14px; }

/* Footer */
.wc-footer { text-align:center; color:#8a8fa6; font-size:.82rem; margin:1.6rem 0 .4rem; }
.wc-footer b { color:var(--wc-purple); }
</style>
"""


def hero_html(title: str, subtitle: str, chip: str) -> str:
    return f"""
<div class="wc-hero">
  <h1><span class="wc-ball">⚽</span>{title}</h1>
  <p>{subtitle}</p>
  <div class="wc-hosts">🇨🇦&nbsp;&nbsp;🇲🇽&nbsp;&nbsp;🇺🇸</div>
  <span class="wc-chip">{chip}</span>
</div>
"""


FOOTER_HTML = (
    '<div class="wc-footer">⚽ <b>Predictor Copa Mundial 2026</b> · '
    "Herramienta analítica y educativa · No es asesoramiento de apuestas · "
    "Datos abiertos (Nivel 0)</div>"
)
