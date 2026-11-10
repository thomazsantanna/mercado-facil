"""Tela de entrada (RNF08: acesso protegido)."""

from __future__ import annotations

import streamlit as st

from ... import config, seed
from ...models import ROLE_LABELS, User
from ...services import auth
from .. import compat, components, state
from ..navigation import default_page


def render() -> None:
    _, center, _ = st.columns([1, 1.4, 1])
    with center:
        components.html(
            f'<div class="mf-brand">🛒 {components.esc(config.APP_NAME)}'
            "<small>Sistema de caixa e gestão de vendas de supermercado</small></div>"
        )
        components.render_flashes()
        st.subheader("Entrar")
        with st.form("login_form"):
            username = st.text_input("Usuário", key="login_username", placeholder="ex.: operador")
            password = st.text_input("Senha", type="password", key="login_password")
            submitted = compat.stretch(st.form_submit_button, "Entrar", type="primary")
        if submitted:
            _attempt(username, password)
        if config.show_demo_users():
            _demo_credentials()


def _attempt(username: str, password: str) -> None:
    def authenticate() -> User:
        with state.db() as conn:
            return auth.authenticate(conn, username, password)

    ok, user = components.run_action(authenticate)
    if ok and user is not None:
        state.login(user)
        state.goto(default_page(user).slug)
        compat.rerun()


def _demo_credentials() -> None:
    with st.expander("Credenciais de demonstração", expanded=True):
        components.alert(
            "info",
            "Perfis de exemplo criados com a base de demonstração. "
            "Defina MERCADO_FACIL_SHOW_DEMO_USERS=0 para ocultar esta tabela.",
        )
        components.lines_table(
            ["Usuário", "Senha", "Perfil"],
            [(u, pwd, ROLE_LABELS.get(role, role)) for u, _, role, pwd in seed.DEMO_USERS],
        )
