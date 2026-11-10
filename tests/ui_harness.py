"""Ambiente de testes da interface: Streamlit simulado + banco temporário + usuários."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from mercadofacil import bootstrap, config, database
from mercadofacil.models import User
from mercadofacil.services import auth
from tests.fake_streamlit import FakeStreamlit

_PREFIXES = ("mercadofacil.ui", "streamlit")


def _owned(name: str) -> bool:
    return any(name == p or name.startswith(p + ".") for p in _PREFIXES)


class UiApp:
    """Fachada para os testes: abre as telas reais sobre o Streamlit simulado."""

    def __init__(self, st: FakeStreamlit) -> None:
        self.st = st

    def module(self, dotted: str) -> ModuleType:
        return importlib.import_module(f"mercadofacil.ui.{dotted}")

    def user(self, username: str) -> User:
        with database.connect() as conn:
            found = auth.reload_user(conn, username)
        assert found is not None
        return found

    def login_as(self, username: str) -> User:
        user = self.user(username)
        self.module("state").login(user)
        return user

    def render(self, view: str, username: str | None = None) -> None:
        """Desenha uma tela (`views.<view>.render`) como o usuário informado."""
        module = self.module(f"views.{view}")
        if view == "login":
            self.st.run(module.render)
            return
        user = self.user(username or "gestor")
        self.st.run(lambda: module.render(user))
        self._assert_no_crash()

    def shell(self) -> None:
        self.st.run(self.module("shell").main)
        self._assert_no_crash()

    def _assert_no_crash(self) -> None:
        """O shell esconde exceções atrás de um aviso; nos testes elas devem aparecer."""
        if "Erro inesperado" in self.st.text():
            trace = next((str(t) for k, t, _ in self.st.elements if k == "code"), "")
            raise AssertionError(f"A tela falhou:\n{trace}")

    # atalhos ---------------------------------------------------------------------------
    def type(self, ident: str, value: Any) -> UiApp:
        self.st.type(ident, value)
        return self

    def click(self, ident: str) -> UiApp:
        self.st.click(ident)
        return self

    def hold(self, ident: str) -> UiApp:
        self.st.hold(ident)
        return self

    def run(self, script: Callable[[], Any]) -> None:
        self.st.run(script)

    def text(self) -> str:
        return self.st.text()

    def contains(self, *fragments: str) -> bool:
        return self.st.contains(*fragments)

    def raw(self) -> str:
        return self.st.raw()


def make_app(version: str, db_path: Path) -> Iterator[UiApp]:
    saved = {name: mod for name, mod in sys.modules.items() if _owned(name)}
    for name in saved:
        del sys.modules[name]
    fake = FakeStreamlit(version)
    sys.modules["streamlit"] = fake
    sys.modules["streamlit.components"] = fake.components
    sys.modules["streamlit.components.v1"] = fake.components.v1  # type: ignore[attr-defined]
    try:
        yield UiApp(fake)
    finally:
        for name in [n for n in sys.modules if _owned(n)]:
            del sys.modules[name]
        sys.modules.update(saved)
        package = sys.modules.get("mercadofacil")
        if package is not None and "mercadofacil.ui" in saved:
            package.ui = saved["mercadofacil.ui"]  # type: ignore[attr-defined]


@pytest.fixture
def ui_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Banco temporário com a demonstração (usuários gestor/operador/estoquista)."""
    config.PBKDF2_ITERATIONS = 1_000
    path = tmp_path / "ui.db"
    monkeypatch.setenv("MERCADO_FACIL_DB", str(path))
    bootstrap.initialize(path)
    return path


@pytest.fixture
def app(ui_db: Path) -> Iterator[UiApp]:
    yield from make_app("1.40.0", ui_db)


@pytest.fixture
def modern_app(ui_db: Path) -> Iterator[UiApp]:
    yield from make_app("1.55.0", ui_db)
