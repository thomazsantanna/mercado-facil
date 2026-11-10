"""Componentes reutilizáveis (6.1): alertas, selos, cartões, tabelas, entradas e navegação."""

from __future__ import annotations

import html as _html
import re
import sqlite3
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

import streamlit as st

from .. import config, errors
from ..models import Product, Register, User
from ..money import parse_money
from ..services import permissions
from . import compat, state
from .formatting import Row

T = TypeVar("T")

_TONES = ("ok", "warn", "danger", "info", "neutral")


# ----------------------------------------------------------------------------- escapes
def esc(text: object) -> str:
    """Escapa texto para HTML. O '$' vira entidade: o markdown do Streamlit o trata como LaTeX."""
    return _html.escape(str(text), quote=True).replace("$", "&#36;")


_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]<>#~|$])")


def md_escape(text: object) -> str:
    """Escapa texto dinâmico para uso em `st.markdown`/`st.caption` (R$ não vira fórmula)."""
    return _MD_SPECIAL.sub(r"\\\1", str(text))


def html(markup: str) -> None:
    """Renderiza HTML. As linhas são unidas porque recuo de 4 espaços viraria bloco de código."""
    st.markdown(
        "".join(line.strip() for line in markup.strip().splitlines()), unsafe_allow_html=True
    )


# ----------------------------------------------------------------------------- blocos HTML
def _tone(tone: str) -> str:
    return tone if tone in _TONES else "neutral"


def alert_markup(
    tone: str, message: str, *, title: str | None = None, items: Sequence[str] = ()
) -> str:
    role = "alert" if tone in ("danger", "warn") else "status"
    parts = [f'<div class="mf-alert mf-alert-{_tone(tone)}" role="{role}">']
    if title:
        parts.append(f"<strong>{esc(title)}</strong>")
    parts.append(f"<span>{esc(message)}</span>")
    if items:
        parts.append("<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>")
    parts.append("</div>")
    return "".join(parts)


def alert(tone: str, message: str, *, title: str | None = None, items: Sequence[str] = ()) -> None:
    """Mensagem em destaque: verde = sucesso, amarelo = atenção, vermelho = erro (7.1)."""
    html(alert_markup(tone, message, title=title, items=items))


def badge_markup(text: str, tone: str = "neutral") -> str:
    return f'<span class="mf-badge mf-badge-{_tone(tone)}">{esc(text)}</span>'


def stock_badge_markup(product: Product) -> str:
    """Selo de estoque do produto: verde (ok), amarelo (repor) ou vermelho (sem estoque)."""
    if product.stock <= 0:
        return badge_markup("Sem estoque", "danger")
    tone = "warn" if product.stock <= product.min_stock else "ok"
    prefix = "Repor · " if tone == "warn" else ""
    return badge_markup(f"{prefix}{product.stock} {product.unit} em estoque", tone)


def metric_markup(label: str, value: str, hint: str = "") -> str:
    hint_html = f'<div class="mf-hint">{esc(hint)}</div>' if hint else ""
    return (
        '<div class="mf-metric">'
        f'<div class="mf-label">{esc(label)}</div>'
        f'<div class="mf-value">{esc(value)}</div>{hint_html}</div>'
    )


def metrics(cards: Sequence[tuple[str, str, str]], per_row: int = 3) -> None:
    """Cartões de indicador (rótulo, valor, dica) distribuídos em linhas."""
    for start in range(0, len(cards), per_row):
        row = cards[start : start + per_row]
        for column, (label, value, hint) in zip(st.columns(per_row), row, strict=False):
            with column:
                html(metric_markup(label, value, hint))


def highlight_markup(kind: str, label: str, value: str) -> str:
    """Destaque do PDV: `kind` é 'total' ou 'change' (7.1)."""
    return (
        f'<div class="mf-{kind}"><div class="mf-label">{esc(label)}</div>'
        f'<div class="mf-value">{esc(value)}</div></div>'
    )


def receipt_markup(text: str) -> str:
    return f'<pre class="mf-receipt">{esc(text)}</pre>'


def receipt_block(text: str) -> None:
    st.markdown(receipt_markup(text), unsafe_allow_html=True)


def empty_state(message: str, hint: str | None = None) -> None:
    """Estado vazio com orientação (RNF06)."""
    extra = f"<br>{esc(hint)}" if hint else ""
    html(f'<div class="mf-card"><strong>{esc(message)}</strong>{extra}</div>')


def section_title(text: str) -> None:
    html(f"<h3>{esc(text)}</h3>")


# ----------------------------------------------------------------------------- cabeçalho
def chip_markup(text: str, tone: str) -> str:
    return f'<span class="mf-chip mf-chip-{tone}">{esc(text)}</span>'


def header_markup(title: str, user: User, register: Register | None) -> str:
    chips = []
    if permissions.can(user, permissions.REGISTER_MANAGE):
        is_open = register is not None and register.is_open
        chips.append(
            chip_markup(
                "● Caixa aberto" if is_open else "● Caixa fechado", "ok" if is_open else "danger"
            )
        )
    chips.append(chip_markup(f"{user.name} · {user.role_label}", "neutral"))
    return (
        f'<div class="mf-header"><h1>{esc(title)}</h1>'
        f'<div class="mf-chips">{"".join(chips)}</div></div>'
    )


def page_header(title: str, user: User, register: Register | None) -> None:
    html(header_markup(title, user, register))


# ------------------------------------------------------------------------------ tabelas
def table(
    rows: Sequence[Row],
    *,
    empty: str = "Nenhum registro encontrado.",
    hint: str | None = None,
    height: int | None = None,
) -> None:
    """Tabela com rolagem horizontal; sem linhas, mostra o estado vazio."""
    if not rows:
        empty_state(empty, hint)
        return
    import pandas as pd

    options: dict[str, Any] = {"hide_index": True}
    if height:
        options["height"] = height
    compat.stretch(st.dataframe, pd.DataFrame(list(rows)), **options)


def lines_markup(
    headers: Sequence[str], rows: Sequence[Sequence[str]], numeric: Sequence[int] = ()
) -> str:
    """Tabela HTML simples (resumos curtos), com cabeçalho e cores explícitas."""

    def cell(tag: str, index: int, value: str) -> str:
        css = ' class="mf-num"' if index in numeric else ""
        return f"<{tag}{css}>{esc(value)}</{tag}>"

    head = "".join(cell("th", i, h) for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(cell("td", i, v) for i, v in enumerate(row)) + "</tr>" for row in rows
    )
    return f'<div class="mf-scroll"><table class="mf-lines"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def lines_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]], numeric: Sequence[int] = ()
) -> None:
    html(lines_markup(headers, rows, numeric))


# ------------------------------------------------------------------------------ entradas
def money_field(
    label: str,
    *,
    key: str,
    default: str = "",
    placeholder: str = "0,00",
    help: str | None = None,
    allow_zero: bool = True,
    show_error: bool = True,
) -> tuple[int | None, str | None]:
    """Campo de valor em reais ('12,50'). Devolve (centavos, mensagem de erro)."""
    if key not in st.session_state:
        st.session_state[key] = default
    text = st.text_input(label, key=key, placeholder=placeholder, help=help)
    if not str(text).strip():
        return None, None
    try:
        return parse_money(text, allow_zero=allow_zero), None
    except errors.ValidationError as exc:
        if show_error:
            alert("warn", str(exc), title="Valor inválido")
        return None, str(exc)


def supervisor_credentials(user: User, key: str) -> tuple[str | None, str | None]:
    """Autorização do gestor para pós-venda: o gestor autoriza a si mesmo; o operador informa."""
    if user.role == config.ROLE_MANAGER:
        alert("info", f"Você é gestor ({user.username}) e autoriza esta operação.")
        return None, None
    alert(
        "warn",
        "Esta operação exige autorização de um gestor. Peça ao gestor que informe usuário e senha.",
        title="Autorização do gestor",
    )
    left, right = st.columns(2)
    username = left.text_input("Usuário do gestor", key=f"{key}_sup_user")
    password = right.text_input("Senha do gestor", type="password", key=f"{key}_sup_pass")
    return username, password


# ------------------------------------------------------------------------------- ações
def error_title(exc: Exception) -> str:
    if isinstance(exc, errors.BusinessRuleError):
        return f"Regra de negócio {exc.rule}" if exc.rule else "Operação não permitida"
    if isinstance(exc, errors.ValidationError):
        return "Confira os dados informados"
    if isinstance(exc, (errors.PermissionDeniedError, errors.AuthenticationError)):
        return "Acesso negado"
    if isinstance(exc, errors.NotFoundError):
        return "Registro não encontrado"
    return "Não foi possível concluir"


def show_error(exc: Exception) -> None:
    alert("danger", str(exc), title=error_title(exc))


def run_action(
    action: Callable[[], T],
    *,
    success: str | Callable[[Any], str] | None = None,
) -> tuple[bool, T | None]:
    """Executa uma operação de serviço exibindo erros de regra de forma clara (RNF06).

    Em caso de sucesso e se `success` for informado, a mensagem é guardada para
    aparecer após o `rerun` que a tela costuma fazer em seguida.
    """
    try:
        result = action()
    except errors.MercadoFacilError as exc:
        show_error(exc)
        return False, None
    except sqlite3.Error:
        alert(
            "danger",
            "O banco de dados não respondeu. Aguarde alguns segundos e tente novamente.",
            title="Falha temporária",
        )
        return False, None
    if success is not None:
        state.flash("ok", success(result) if callable(success) else success)
    return True, result


def render_flashes() -> None:
    for tone, message in state.pop_flashes():
        alert(tone, message)
