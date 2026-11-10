"""Estado da sessão do navegador (st.session_state) e acesso ao banco."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st

from .. import database
from ..models import User

KEY_USER = "auth_user"
KEY_PAGE = "nav_page"
KEY_FLASH = "flash_messages"

Flash = tuple[str, str]  # (tom, mensagem)


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    """Conexão curta para uma operação (o SQLite abre em microssegundos).

    Cada execução do script — e cada diálogo, que reexecuta sozinho — abre a sua
    conexão e a fecha ao final, sem compartilhar estado entre usuários.
    """
    with database.connect() as conn:
        yield conn


def current_user() -> User | None:
    user = st.session_state.get(KEY_USER)
    return user if isinstance(user, User) else None


def login(user: User) -> None:
    st.session_state[KEY_USER] = user


def logout() -> None:
    """Encerra a sessão e descarta todo o estado (carrinho, filtros, mensagens)."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def flash(tone: str, message: str) -> None:
    """Guarda uma mensagem para a próxima execução (após `st.rerun`)."""
    queue: list[Flash] = st.session_state.setdefault(KEY_FLASH, [])
    queue.append((tone, message))


def pop_flashes() -> list[Flash]:
    queue: list[Flash] = st.session_state.get(KEY_FLASH, [])
    st.session_state[KEY_FLASH] = []
    return queue


def goto(slug: str) -> None:
    """Troca de página. Use como `on_click` (callback) para evitar conflito com widgets."""
    st.session_state[KEY_PAGE] = slug
