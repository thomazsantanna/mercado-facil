"""Paleta, verificação de contraste (WCAG 2.1) e CSS da interface.

Regra de ouro: toda cor de texto é declarada **junto** com a sua cor de fundo.
Por isso os pares ficam centralizados em `TEXT_PAIRS`/`UI_PAIRS` e o CSS é
gerado a partir deles; o teste `tests/test_ui_theme.py` calcula a razão de
contraste de cada par (mínimo 4,5:1 para texto e 3:1 para bordas de controles),
de modo que nenhum elemento fique ilegível por ter a cor do fundo.
"""

from __future__ import annotations

from string import Template

# ------------------------------------------------------------------------- Paleta base
INK = "#17261D"  # texto principal
INK_MUTED = "#47564D"  # texto secundário
PLACEHOLDER = "#5A685F"
PAGE_BG = "#FFFFFF"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F1F5F2"  # cartões
SIDEBAR_BG = "#EAF0EB"  # = secondaryBackgroundColor em .streamlit/config.toml
BORDER_SOFT = "#C3CEC6"  # decoração (cartões)
BORDER_STRONG = "#5F6F65"  # controles interativos (>= 3:1 sobre branco)

PRIMARY = "#0B6E3C"
PRIMARY_DARK = "#074F2A"
ON_PRIMARY = "#FFFFFF"

HOVER_BG = "#E4F1E8"
DISABLED_BG = "#E1E7E3"
DISABLED_FG = "#46564C"
DISABLED_BORDER = "#8D9C92"

# Tons semânticos (7.1: verde = concluído/entrada, amarelo = atenção, vermelho = erro).
# tom -> (texto, fundo, borda)
TONES: dict[str, tuple[str, str, str]] = {
    "ok": ("#0A5A2E", "#DDF3E4", "#1F8A4C"),
    "warn": ("#5C3F00", "#FFF0BF", "#B88700"),
    "danger": ("#8A1C1C", "#FDE3E3", "#C0392B"),
    "info": ("#0B4A7A", "#DDEBFA", "#2B76B9"),
    "neutral": ("#2B3A31", "#E5EAE6", "#5F6F65"),
}

# Selos "sólidos" (cabeçalho: caixa aberto/fechado).
SOLID: dict[str, tuple[str, str]] = {
    "ok": ("#FFFFFF", "#0B6E3C"),
    "danger": ("#FFFFFF", "#A32020"),
    "neutral": ("#FFFFFF", "#3B4A41"),
}

# Destaques do PDV (7.1: total e troco com destaque).
TOTAL_FG, TOTAL_BG = "#FFFFFF", "#0B3D22"
CHANGE_FG, CHANGE_BG, CHANGE_BORDER = "#0A3A1F", "#CFF1D9", "#1F8A4C"
RECEIPT_FG, RECEIPT_BG, RECEIPT_BORDER = "#1B1B1B", "#FFFDF4", "#B9B49A"

# Pares (texto, fundo) que precisam de contraste >= 4,5:1.
TEXT_PAIRS: dict[str, tuple[str, str]] = {
    "texto/página": (INK, PAGE_BG),
    "texto/cartão": (INK, SURFACE_ALT),
    "texto/barra lateral": (INK, SIDEBAR_BG),
    "texto secundário/página": (INK_MUTED, PAGE_BG),
    "texto secundário/cartão": (INK_MUTED, SURFACE_ALT),
    "texto secundário/barra lateral": (INK_MUTED, SIDEBAR_BG),
    "placeholder/campo": (PLACEHOLDER, SURFACE),
    "botão primário": (ON_PRIMARY, PRIMARY),
    "botão primário (hover)": (ON_PRIMARY, PRIMARY_DARK),
    "botão secundário": (INK, SURFACE),
    "botão secundário/barra lateral": (INK, SURFACE),
    "botão secundário (hover)": (INK, HOVER_BG),
    "botão desabilitado": (DISABLED_FG, DISABLED_BG),
    "aba selecionada": (PRIMARY, PAGE_BG),
    "total do PDV": (TOTAL_FG, TOTAL_BG),
    "troco do PDV": (CHANGE_FG, CHANGE_BG),
    "comprovante": (RECEIPT_FG, RECEIPT_BG),
    **{f"selo {name}": (fg, bg) for name, (fg, bg, _) in TONES.items()},
    **{f"selo sólido {name}": pair for name, pair in SOLID.items()},
}

# Pares (borda/ícone, fundo) que precisam de contraste >= 3:1 (WCAG 1.4.11).
UI_PAIRS: dict[str, tuple[str, str]] = {
    "borda de campo/página": (BORDER_STRONG, PAGE_BG),
    "borda de campo/barra lateral": (BORDER_STRONG, SIDEBAR_BG),
    "borda de botão secundário": (BORDER_STRONG, SURFACE),
    "foco/botão primário": (PRIMARY, PAGE_BG),
}


# ---------------------------------------------------------------------------- Contraste
def _channel(value: int) -> float:
    scaled = value / 255
    return scaled / 12.92 if scaled <= 0.03928 else ((scaled + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    """Luminância relativa de '#RRGGBB' (WCAG 2.1)."""
    text = color.lstrip("#")
    if len(text) != 6:
        raise ValueError(f"Cor inválida: {color!r}")
    red, green, blue = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    """Razão de contraste entre duas cores (1 a 21)."""
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


# ------------------------------------------------------------------------------- CSS
_CSS = Template(
    """
/* ---------- base ---------- */
.block-container { padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1400px; }
h1, h2, h3, h4, h5 { color: $INK; letter-spacing: -0.01em; }
[data-testid="stSidebar"] { border-right: 1px solid $BORDER_SOFT; }
[data-testid="stCaptionContainer"], .stCaption { color: $INK_MUTED; }

/* ---------- botões (alvo de toque >= 44px, borda visível) ---------- */
.stButton > button, .stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button {
  min-height: 2.75rem; border-radius: 10px; font-weight: 600;
  border: 1.5px solid $BORDER_STRONG;
}
.stButton > button *, .stDownloadButton > button *,
[data-testid="stFormSubmitButton"] > button * { color: inherit !important; }
.stButton > button[kind="secondary"], .stDownloadButton > button[kind="secondary"],
[data-testid="stFormSubmitButton"] > button[kind="secondary"],
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
  background: $SURFACE; color: $INK; border: 1.5px solid $BORDER_STRONG;
}
.stButton > button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover {
  background: $HOVER_BG; color: $INK; border-color: $PRIMARY;
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] > button[kind="primary"],
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: $PRIMARY; color: $ON_PRIMARY; border: 1.5px solid $PRIMARY_DARK;
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  background: $PRIMARY_DARK; color: $ON_PRIMARY; border-color: $PRIMARY_DARK;
}
.stButton > button:disabled, .stDownloadButton > button:disabled,
[data-testid="stFormSubmitButton"] > button:disabled {
  background: $DISABLED_BG; color: $DISABLED_FG; border-color: $DISABLED_BORDER; opacity: 1;
}
button:focus-visible, input:focus-visible, textarea:focus-visible {
  outline: 3px solid $PRIMARY; outline-offset: 2px;
}

/* ---------- campos (fundo branco e borda forte: nunca "somem" na página) ---------- */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-baseweb="select"] > div {
  background: $SURFACE !important; border-color: $BORDER_STRONG !important;
  border-width: 1.5px !important; border-radius: 8px !important;
}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea,
[data-baseweb="select"] input, [data-baseweb="select"] div {
  color: $INK; background: transparent;
}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea { min-height: 2.5rem; }
input::placeholder, textarea::placeholder { color: $PLACEHOLDER; opacity: 1; }
[data-testid="stWidgetLabel"] p, label p { color: $INK; font-weight: 600; }

/* ---------- abas ---------- */
button[data-baseweb="tab"] p { color: $INK_MUTED; font-weight: 600; }
button[data-baseweb="tab"][aria-selected="true"] p { color: $PRIMARY; }

/* ---------- componentes próprios ---------- */
.mf-scroll { overflow-x: auto; }
.mf-brand { background: $PRIMARY; color: $ON_PRIMARY; border-radius: 12px; padding: 0.8rem 1rem;
  font-weight: 800; font-size: 1.25rem; line-height: 1.2; }
.mf-brand small { display: block; font-weight: 500; font-size: 0.8rem; opacity: 1; }
.mf-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
  gap: 0.6rem; margin: 0 0 0.9rem 0; }
.mf-header h1 { margin: 0; padding: 0; font-size: 1.8rem; color: $INK; }
.mf-chips { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
.mf-chip { display: inline-flex; align-items: center; gap: 0.35rem; border-radius: 999px;
  padding: 0.3rem 0.8rem; font-weight: 700; font-size: 0.9rem; white-space: nowrap; }
.mf-chip-ok { color: ${SOLID_OK_FG}; background: ${SOLID_OK_BG}; }
.mf-chip-danger { color: ${SOLID_DANGER_FG}; background: ${SOLID_DANGER_BG}; }
.mf-chip-neutral { color: ${SOLID_NEUTRAL_FG}; background: ${SOLID_NEUTRAL_BG}; }
.mf-badge { display: inline-block; border-radius: 6px; padding: 0.1rem 0.5rem; font-weight: 700;
  font-size: 0.85rem; border: 1px solid transparent; }
.mf-alert { border-radius: 10px; padding: 0.75rem 1rem; margin: 0.4rem 0 0.8rem 0;
  border-left: 6px solid transparent; line-height: 1.45; }
.mf-alert strong { display: block; margin-bottom: 0.15rem; }
.mf-alert ul { margin: 0.3rem 0 0 1.1rem; padding: 0; }
.mf-card { border-radius: 12px; padding: 0.8rem 1rem; background: $SURFACE_ALT; color: $INK;
  border: 1px solid $BORDER_SOFT; }
.mf-metric { border-radius: 12px; padding: 0.8rem 1rem; background: $SURFACE_ALT; color: $INK;
  border: 1px solid $BORDER_SOFT; height: 100%; }
.mf-metric .mf-label { color: $INK_MUTED; font-size: 0.85rem; font-weight: 600; }
.mf-metric .mf-value { color: $INK; font-size: 1.6rem; font-weight: 800; line-height: 1.2; }
.mf-metric .mf-hint { color: $INK_MUTED; font-size: 0.8rem; }
.mf-total { border-radius: 14px; padding: 0.9rem 1.1rem; background: $TOTAL_BG; color: $TOTAL_FG;
  margin: 0.4rem 0; }
.mf-total .mf-label { color: $TOTAL_FG; font-size: 0.9rem; font-weight: 600; }
.mf-total .mf-value { color: $TOTAL_FG; font-size: 2.3rem; font-weight: 800; line-height: 1.15; }
.mf-change { border-radius: 14px; padding: 0.8rem 1.1rem; background: $CHANGE_BG; color: $CHANGE_FG;
  border: 2px solid $CHANGE_BORDER; margin: 0.4rem 0; }
.mf-change .mf-label { color: $CHANGE_FG; font-size: 0.9rem; font-weight: 700; }
.mf-change .mf-value { color: $CHANGE_FG; font-size: 2rem; font-weight: 800; line-height: 1.15; }
.mf-lines { width: 100%; border-collapse: collapse; color: $INK; background: $SURFACE; }
.mf-lines th { text-align: left; color: $INK; background: $SIDEBAR_BG; padding: 0.4rem 0.6rem;
  border-bottom: 2px solid $BORDER_STRONG; font-size: 0.85rem; }
.mf-lines td { padding: 0.4rem 0.6rem; border-bottom: 1px solid $BORDER_SOFT; color: $INK; }
.mf-lines td.mf-num, .mf-lines th.mf-num { text-align: right; white-space: nowrap; }
.mf-receipt { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.85rem; line-height: 1.35; white-space: pre; overflow-x: auto; margin: 0.3rem 0;
  background: $RECEIPT_BG; color: $RECEIPT_FG; border: 1px dashed $RECEIPT_BORDER;
  border-radius: 8px; padding: 0.9rem 1rem; }
$TONE_RULES
@media (max-width: 640px) {
  .mf-header h1 { font-size: 1.4rem; }
  .mf-total .mf-value { font-size: 1.9rem; }
}
"""
)


def _tone_rules() -> str:
    rules = []
    for name, (fg, bg, border) in TONES.items():
        rules.append(
            f".mf-badge-{name} {{ color: {fg}; background: {bg}; border-color: {border}; }}"
        )
        rules.append(
            f".mf-alert-{name} {{ color: {fg}; background: {bg}; border-left-color: {border}; }}"
        )
    return "\n".join(rules)


def build_css() -> str:
    """CSS completo (cada regra de cor define texto e fundo juntos)."""
    values = {
        "INK": INK,
        "INK_MUTED": INK_MUTED,
        "PLACEHOLDER": PLACEHOLDER,
        "SURFACE": SURFACE,
        "SURFACE_ALT": SURFACE_ALT,
        "SIDEBAR_BG": SIDEBAR_BG,
        "BORDER_SOFT": BORDER_SOFT,
        "BORDER_STRONG": BORDER_STRONG,
        "PRIMARY": PRIMARY,
        "PRIMARY_DARK": PRIMARY_DARK,
        "ON_PRIMARY": ON_PRIMARY,
        "HOVER_BG": HOVER_BG,
        "DISABLED_BG": DISABLED_BG,
        "DISABLED_FG": DISABLED_FG,
        "DISABLED_BORDER": DISABLED_BORDER,
        "TOTAL_FG": TOTAL_FG,
        "TOTAL_BG": TOTAL_BG,
        "CHANGE_FG": CHANGE_FG,
        "CHANGE_BG": CHANGE_BG,
        "CHANGE_BORDER": CHANGE_BORDER,
        "RECEIPT_FG": RECEIPT_FG,
        "RECEIPT_BG": RECEIPT_BG,
        "RECEIPT_BORDER": RECEIPT_BORDER,
        "SOLID_OK_FG": SOLID["ok"][0],
        "SOLID_OK_BG": SOLID["ok"][1],
        "SOLID_DANGER_FG": SOLID["danger"][0],
        "SOLID_DANGER_BG": SOLID["danger"][1],
        "SOLID_NEUTRAL_FG": SOLID["neutral"][0],
        "SOLID_NEUTRAL_BG": SOLID["neutral"][1],
        "TONE_RULES": _tone_rules(),
    }
    return _CSS.substitute(values)
