"""Camada de compatibilidade com diferentes versões do Streamlit (>= 1.40).

O Streamlit muda parâmetros com frequência (por exemplo, `use_container_width`
foi substituído por `width="stretch"`). Todo o restante da interface chama o
Streamlit por aqui, de modo que um ajuste de versão fica concentrado em um só
arquivo.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from typing import Any, TypeVar

import streamlit as st

F = TypeVar("F", bound=Callable[..., Any])


def _version() -> tuple[int, int]:
    parts = str(getattr(st, "__version__", "0.0")).split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0


#: A partir desta versão `width="stretch"` é o modo preferido (e `use_container_width` é legado).
PREFERS_WIDTH_STRETCH = _version() >= (1, 50)


def stretch(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Chama um elemento com largura total do contêiner, na sintaxe da versão instalada."""
    if PREFERS_WIDTH_STRETCH:
        try:
            return fn(*args, width="stretch", **kwargs)
        except (TypeError, st.errors.StreamlitAPIException):
            pass
    return fn(*args, use_container_width=True, **kwargs)


def rerun() -> None:
    """Reexecuta o script imediatamente."""
    st.rerun()


def dialog(title: str) -> Callable[[F], F]:
    """Decorador de diálogo modal (`st.dialog`); sem suporte, abre um painel na própria página."""
    factory = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if factory is not None:
        return factory(title, width="large")

    def decorate(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with st.container(border=True):
                st.subheader(title)
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorate


def toast(message: str, icon: str | None = None) -> None:
    """Aviso passageiro; versões antigas exibem uma mensagem comum."""
    notify = getattr(st, "toast", None)
    if notify is None:  # pragma: no cover - Streamlit < 1.27
        st.info(message)
        return
    notify(message, icon=icon)


def focus_input(label: str, nonce: int = 0) -> None:
    """Leva o foco do teclado ao campo cujo rótulo é `label` (leitor de código de barras).

    É um recurso de conveniência, melhor esforço: se o navegador ou a versão do
    Streamlit não permitir, nada acontece e o operador apenas clica no campo.
    """
    script = (
        "<script>"
        f"/* {int(nonce)} */"
        f"const label = {json.dumps(label)};"
        "let tries = 0;"
        "const timer = setInterval(() => {"
        "  try {"
        "    const doc = window.parent.document;"
        "    const el = doc.querySelector('input[aria-label=' + JSON.stringify(label) + ']');"
        "    if (el) { el.focus(); if (el.select) { el.select(); } clearInterval(timer); }"
        "  } catch (e) { clearInterval(timer); }"
        "  if (++tries > 25) { clearInterval(timer); }"
        "}, 120);"
        "</script>"
    )
    try:
        import streamlit.components.v1 as components

        components.html(script, height=0)
    except Exception:  # recurso opcional; qualquer falha é ignorada
        return
