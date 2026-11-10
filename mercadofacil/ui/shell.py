"""Estrutura da aplicação: configuração da página, login, navegação lateral e cabeçalho."""

from __future__ import annotations

import importlib
import traceback

import streamlit as st

from .. import bootstrap, config
from ..models import User
from ..services import auth, cash_register, permissions
from . import compat, components, state, theme
from .navigation import Page, default_page, get_page, visible_pages
from .views import login


@st.cache_resource(show_spinner=False)
def _initialize_database(path: str) -> str:
    """Cria o esquema e os dados de demonstração uma única vez por processo."""
    return str(bootstrap.initialize(path))


def _ensure_database() -> None:
    path = config.get_db_path()
    if not path.exists():
        _initialize_database.clear()
    _initialize_database(str(path))


def _refresh_user() -> User | None:
    """Recarrega o usuário da sessão; contas desativadas perdem o acesso na hora."""
    stored = state.current_user()
    if stored is None:
        return None
    with state.db() as conn:
        fresh = auth.reload_user(conn, stored.username)
    if fresh is None:
        state.logout()
        state.flash("warn", "Sua sessão foi encerrada: o usuário não está mais ativo.")
        return None
    state.login(fresh)
    return fresh


def _current_page(user: User) -> Page:
    page = get_page(str(st.session_state.get(state.KEY_PAGE, "")))
    allowed = visible_pages(user)
    if page is None or page not in allowed:
        page = default_page(user)
        st.session_state[state.KEY_PAGE] = page.slug
    return page


def _sidebar(user: User, current: Page) -> None:
    with st.sidebar:
        components.html(
            f'<div class="mf-brand">🛒 {components.esc(config.APP_NAME)}'
            "<small>Caixa e gestão de vendas</small></div>"
        )
        st.write("")
        for page in visible_pages(user):
            compat.stretch(
                st.button,
                f"{page.icon}  {page.title}",
                key=f"nav_{page.slug}",
                type="primary" if page.slug == current.slug else "secondary",
                on_click=state.goto,
                args=(page.slug,),
            )
        st.divider()
        st.caption(components.md_escape(f"Conectado como {user.name} ({user.role_label})"))
        compat.stretch(st.button, "Sair", key="logout", on_click=state.logout)


def _render_page(page: Page, user: User) -> None:
    module = importlib.import_module(f"{__package__}.views.{page.slug}")
    try:
        module.render(user)
    except Exception as exc:  # última barreira: nunca mostrar tela quebrada
        components.alert(
            "danger",
            "Ocorreu um erro inesperado nesta tela. Nenhum dado foi perdido; "
            "tente novamente ou avise o responsável pelo sistema.",
            title="Erro inesperado",
        )
        with st.expander("Detalhes técnicos"):
            st.code("".join(traceback.format_exception(exc)), language="text")


def main() -> None:
    st.set_page_config(
        page_title=config.APP_NAME,
        page_icon="🛒",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(f"<style>{theme.build_css()}</style>", unsafe_allow_html=True)
    _ensure_database()

    user = _refresh_user()
    if user is None:
        login.render()
        return

    page = _current_page(user)
    register = None
    if permissions.can(user, permissions.REGISTER_MANAGE):
        with state.db() as conn:
            register = cash_register.get_open_register(conn, user.username)

    _sidebar(user, page)
    components.page_header(page.title, user, register)
    components.render_flashes()
    _render_page(page, user)
