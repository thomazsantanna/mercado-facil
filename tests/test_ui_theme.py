"""Legibilidade: contraste de todas as cores (WCAG AA) e regras de CSS (RNF01, RNF07).

Esses testes existem porque elementos com a cor do fundo ficam ilegíveis: todo par
(texto, fundo) usado pela interface é calculado aqui.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mercadofacil.ui import theme

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "mercadofacil" / "ui"


@pytest.mark.parametrize(("name", "pair"), sorted(theme.TEXT_PAIRS.items()))
def test_pares_de_texto_tem_contraste_minimo_wcag_aa(name: str, pair: tuple[str, str]) -> None:
    assert theme.contrast_ratio(*pair) >= 4.5, f"{name}: {pair}"


@pytest.mark.parametrize(("name", "pair"), sorted(theme.UI_PAIRS.items()))
def test_bordas_de_controles_tem_contraste_minimo_de_3_para_1(
    name: str, pair: tuple[str, str]
) -> None:
    assert theme.contrast_ratio(*pair) >= 3.0, f"{name}: {pair}"


def test_calculo_de_contraste_confere_com_valores_conhecidos() -> None:
    assert theme.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert theme.contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)
    assert theme.contrast_ratio("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)
    with pytest.raises(ValueError):
        theme.relative_luminance("vermelho")


def test_nenhum_texto_tem_a_mesma_cor_do_fundo() -> None:
    for name, (fg, bg) in theme.TEXT_PAIRS.items():
        assert fg.lower() != bg.lower(), name


def test_css_nao_deixa_variaveis_sem_substituir() -> None:
    css = theme.build_css()
    assert "$" not in css
    assert css.count("{") == css.count("}")


def _rules(css: str) -> list[tuple[str, str]]:
    return re.findall(r"([^{}]+)\{([^{}]*)\}", css)


def test_toda_caixa_propria_que_define_cor_de_texto_define_tambem_o_fundo() -> None:
    """Componentes `.mf-*` com cor de texto sempre trazem fundo explícito (nunca "herdam" cor)."""
    sem_fundo = []
    for selector, body in _rules(theme.build_css()):
        selector = selector.strip()
        caixa_propria = re.fullmatch(r"\.mf-[a-z-]+", selector) is not None
        botao = "button[kind" in selector or "stBaseButton" in selector
        tem_cor = re.search(r"(?<![-\w])color\s*:", body) is not None
        if (caixa_propria or botao) and tem_cor and "background" not in body:
            sem_fundo.append(selector)
    assert not sem_fundo, sem_fundo


def test_campos_tem_fundo_branco_e_borda_forte() -> None:
    css = theme.build_css()
    campo = re.search(r"\[data-baseweb=\"input\"\][^{]*\{([^}]*)\}", css)
    assert campo is not None
    assert theme.SURFACE in campo.group(1) and theme.BORDER_STRONG in campo.group(1)


def test_css_garante_alvo_de_toque_e_foco_visivel() -> None:
    css = theme.build_css()
    assert "min-height: 2.75rem" in css  # >= 44 px (RNF07)
    assert ":focus-visible" in css and "outline: 3px solid" in css
    assert "@media (max-width: 640px)" in css  # ajustes para celular (RNF01)
    assert ".mf-scroll { overflow-x: auto; }" in css  # tabelas com rolagem horizontal (7.1)


def test_toda_classe_mf_usada_no_codigo_existe_no_css() -> None:
    css = theme.build_css()
    defined = set(re.findall(r"\.(mf-[a-z-]+)", css))
    used: set[str] = set()
    for path in UI.rglob("*.py"):
        if path.name == "theme.py":
            continue
        used |= set(re.findall(r"\b(mf-[a-z]+(?:-[a-z]+)*)\b", path.read_text(encoding="utf-8")))
    # classes montadas dinamicamente: mf-badge-<tom>, mf-alert-<tom>, mf-chip-<tom>, mf-<kind>
    dynamic = {f"mf-{prefix}-{tone}" for prefix in ("badge", "alert") for tone in theme.TONES} | {
        "mf-chip-ok",
        "mf-chip-danger",
        "mf-chip-neutral",
        "mf-total",
        "mf-change",
    }
    missing = {c for c in used - dynamic if c not in defined and not c.endswith("-")}
    assert not missing, missing


def test_config_toml_define_tema_claro_igual_a_paleta() -> None:
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    ui = config["theme"]
    assert ui["base"] == "light"
    assert ui["primaryColor"].lower() == theme.PRIMARY.lower()
    assert ui["backgroundColor"].lower() == theme.PAGE_BG.lower()
    assert ui["secondaryBackgroundColor"].lower() == theme.SIDEBAR_BG.lower()
    assert ui["textColor"].lower() == theme.INK.lower()
    for name in ("primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor"):
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", ui[name])
    assert theme.contrast_ratio(ui["textColor"], ui["backgroundColor"]) >= 7
    assert theme.contrast_ratio(ui["textColor"], ui["secondaryBackgroundColor"]) >= 7
