"""Simulador mínimo do Streamlit para testar as telas sem abrir um navegador.

Não substitui testar no Streamlit real: ele valida a **lógica** das telas (que
mensagens aparecem, que serviços são chamados, o que muda no estado) e reproduz
três regras do Streamlit que costumam causar defeitos:

1. callbacks (`on_click`/`on_change`) rodam ANTES do script da execução seguinte;
2. alterar `st.session_state[chave]` de um widget já criado na execução levanta erro;
3. o estado de um widget que não foi desenhado numa execução é descartado.

Uso:  app.type("chave", "texto") · app.click("chave") · app.run(funcao) · app.text()
"""

from __future__ import annotations

import html as html_lib
import re
import types
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any


class StreamlitAPIException(Exception):
    pass


class RerunException(BaseException):
    pass


class _State(dict[str, Any]):
    """session_state: acesso por item e por atributo; protege widgets já criados."""

    def __init__(self, app: FakeStreamlit) -> None:
        super().__init__()
        object.__setattr__(self, "_app", app)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self._app._instantiated:
            raise StreamlitAPIException(
                f"`st.session_state.{key}` não pode ser alterado depois que o widget com essa "
                "chave foi criado."
            )
        super().__setitem__(key, value)

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _Context:
    """Contêiner (coluna, expander, form…): também expõe os widgets, como o DeltaGenerator."""

    def __init__(self, app: FakeStreamlit, kind: str, label: str = "") -> None:
        self._app = app
        self.kind = kind
        self.label = label

    def __enter__(self) -> _Context:
        self._app._record(f"enter:{self.kind}", self.label)
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._app, name)


class FakeStreamlit(types.ModuleType):
    def __init__(self, version: str = "1.40.0") -> None:
        super().__init__("streamlit")
        self.__version__ = version
        self.errors = types.SimpleNamespace(StreamlitAPIException=StreamlitAPIException)
        self.session_state = _State(self)
        self.elements: list[tuple[str, Any, dict[str, Any]]] = []
        self.dataframes: list[Any] = []
        self.downloads: list[dict[str, Any]] = []
        self._instantiated: set[str] = set()
        self._widget_keys: set[str] = set()
        self._callbacks: dict[
            str, list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]]
        ] = {}
        self._labels: dict[str, str] = {}  # rótulo -> identificador (chave) da última execução
        self._options: dict[str, tuple[list[Any], Callable[[Any], str]]] = {}
        self._pending: dict[str, Any] = {}
        self._clicks: set[str] = set()
        self._sticky: set[str] = set()  # cliques mantidos (diálogo aberto)
        self._form_stack: list[tuple[str, bool]] = []
        self._form_members: dict[str, list[str]] = {}
        self._clear_after: list[str] = []
        self._cache: dict[Callable[..., Any], dict[Any, Any]] = {}
        self.sidebar = _Context(self, "sidebar")
        self.components = types.ModuleType("streamlit.components")
        self.components.v1 = types.ModuleType("streamlit.components.v1")  # type: ignore[attr-defined]
        self.components.v1.html = self._iframe  # type: ignore[attr-defined]

    # ----------------------------------------------------------------------- execução
    def type(self, ident: str, value: Any) -> None:
        """Simula o usuário digitando/escolhendo `value` no widget (chave ou rótulo)."""
        self._pending[ident] = value

    def click(self, ident: str) -> None:
        """Simula o clique no botão (chave ou rótulo)."""
        self._clicks.add(ident)

    def hold(self, ident: str) -> None:
        """Mantém o botão 'clicado' em todas as execuções (diálogo aberto) até um rerun."""
        self._sticky.add(ident)

    def run(self, script: Callable[[], Any], *, max_reruns: int = 10) -> None:
        """Executa o script como o Streamlit: callbacks primeiro, depois o corpo."""
        self._instantiated = set()  # callbacks rodam antes de qualquer widget da nova execução
        self._apply_pending_inputs()
        self._run_callbacks()
        for _ in range(max_reruns):
            self.elements.clear()
            self.dataframes.clear()
            self.downloads.clear()
            self._instantiated = set()
            try:
                script()
            except RerunException:
                self._clicks.clear()
                self._sticky.clear()  # um rerun completo fecha o diálogo
                self._finish_run()
                continue
            self._finish_run()
            self._clicks.clear()
            return
        raise AssertionError("Reexecução em laço: o script pediu rerun demais.")

    def _apply_pending_inputs(self) -> None:
        for ident, value in list(self._pending.items()):
            key = self._labels.get(ident, ident)
            dict.__setitem__(self.session_state, key, value)
            for callback in self._callbacks.get(f"change:{key}", []):
                callback[0](*callback[1], **callback[2])
        self._pending.clear()

    def _run_callbacks(self) -> None:
        for ident in list(self._clicks):
            key = self._labels.get(ident, ident)
            for fn, args, kwargs in self._callbacks.get(f"click:{key}", []):
                fn(*args, **kwargs)

    def _finish_run(self) -> None:
        for key in list(
            self._widget_keys - self._instantiated
        ):  # estado de widget ausente é descartado
            dict.pop(self.session_state, key, None)
            self._widget_keys.discard(key)
        for key in self._clear_after:
            dict.pop(self.session_state, key, None)
        self._clear_after.clear()

    # ---------------------------------------------------------------------- consultas
    def _record(self, kind: str, text: Any = "", **props: Any) -> None:
        self.elements.append((kind, text, props))

    def text(self) -> str:
        """Texto visível: HTML sem tags, entidades convertidas e rótulos de widgets."""
        chunks: list[str] = []
        for kind, text, props in self.elements:
            if kind.startswith("enter:"):
                chunks.append(str(text))
            elif kind == "iframe":
                continue
            else:
                chunks.append(str(text))
            chunks.extend(str(v) for k, v in props.items() if k in {"caption", "help", "label"})
        raw = "\n".join(chunks)
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"\\([\\`*_{}\[\]<>#~|$])", r"\1", raw)  # escapes do markdown
        return re.sub(r"[ \t]+", " ", html_lib.unescape(raw))

    def contains(self, *fragments: str) -> bool:
        visible = self.text()
        return all(fragment in visible for fragment in fragments)

    def labels(self, kind: str) -> list[str]:
        return [str(t) for k, t, _ in self.elements if k == kind]

    def raw(self) -> str:
        return "\n".join(str(t) for _, t, _ in self.elements)

    # ---------------------------------------------------------------------- widgets
    def _widget(
        self,
        kind: str,
        label: str,
        key: str | None,
        default: Any,
        *,
        on_change: Callable[..., Any] | None = None,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        **props: Any,
    ) -> Any:
        ident = key or f"{kind}:{label}"
        self._labels[label] = ident
        self._instantiated.add(ident)
        self._widget_keys.add(ident)
        if ident not in self.session_state:
            dict.__setitem__(self.session_state, ident, default)
        if on_change is not None:
            self._callbacks[f"change:{ident}"] = [(on_change, args, kwargs or {})]
        if self._form_stack:
            self._form_members.setdefault(self._form_stack[-1][0], []).append(ident)
        self._record(kind, label, **props)
        return self.session_state[ident]

    def text_input(self, label: str, value: str = "", key: str | None = None, **kw: Any) -> str:
        return str(self._widget("text_input", label, key, value, **self._widget_kw(kw)))

    def text_area(self, label: str, value: str = "", key: str | None = None, **kw: Any) -> str:
        return str(self._widget("text_area", label, key, value, **self._widget_kw(kw)))

    def number_input(self, label: str, *, value: Any = 0, key: str | None = None, **kw: Any) -> Any:
        return self._widget("number_input", label, key, value, **self._widget_kw(kw))

    def checkbox(self, label: str, value: bool = False, key: str | None = None, **kw: Any) -> bool:
        return bool(self._widget("checkbox", label, key, value, **self._widget_kw(kw)))

    def date_input(self, label: str, value: Any = None, key: str | None = None, **kw: Any) -> Any:
        return self._widget("date_input", label, key, value, **self._widget_kw(kw))

    def selectbox(
        self,
        label: str,
        options: Any,
        index: int = 0,
        format_func: Callable[[Any], str] = str,
        key: str | None = None,
        **kw: Any,
    ) -> Any:
        return self._choice("selectbox", label, options, index, format_func, key, kw)

    def radio(
        self,
        label: str,
        options: Any,
        index: int = 0,
        format_func: Callable[[Any], str] = str,
        key: str | None = None,
        **kw: Any,
    ) -> Any:
        return self._choice("radio", label, options, index, format_func, key, kw)

    def _choice(
        self,
        kind: str,
        label: str,
        options: Any,
        index: int,
        format_func: Callable[[Any], str],
        key: str | None,
        kw: dict[str, Any],
    ) -> Any:
        items = list(options)
        ident = key or f"{kind}:{label}"
        default = items[index] if items else None
        current = self.session_state.get(ident, default)
        if current not in items and ident in self.session_state:
            raise StreamlitAPIException(f"O valor {current!r} de “{label}” não está nas opções.")
        self._options[ident] = (items, format_func)
        value = self._widget(kind, label, key, default, **self._widget_kw(kw))
        self._record("options", " | ".join(format_func(o) for o in items))
        return value

    def choose(self, ident: str, label: str) -> None:
        """Escolhe, pelo texto exibido, uma opção de selectbox/radio da última execução."""
        key = self._labels.get(ident, ident)
        items, fmt = self._options[key]
        matches = [o for o in items if label in fmt(o)]
        assert matches, f"Nenhuma opção contém {label!r}: {[fmt(o) for o in items]}"
        self.type(ident, matches[0])

    def button(self, label: str, key: str | None = None, **kw: Any) -> bool:
        return self._button("button", label, key, kw)

    def form_submit_button(self, label: str, **kw: Any) -> bool:
        return self._button("form_submit_button", label, kw.pop("key", None), kw)

    def _button(self, kind: str, label: str, key: str | None, kw: dict[str, Any]) -> bool:
        self._check_width(kw)
        ident = key or f"{kind}:{label}"
        self._labels[label] = ident
        self._instantiated.add(ident)
        if kw.get("on_click") is not None:
            self._callbacks[f"click:{ident}"] = [
                (kw["on_click"], tuple(kw.get("args") or ()), dict(kw.get("kwargs") or {}))
            ]
        else:
            self._callbacks.pop(f"click:{ident}", None)
        self._record(kind, label, disabled=bool(kw.get("disabled")))
        clicked = (
            ident in self._clicks or label in self._clicks or ident in self._sticky
        ) and not kw.get("disabled")
        if clicked and kind == "form_submit_button" and self._form_stack:
            form_key, clear = self._form_stack[-1]
            if clear:
                self._clear_after.extend(self._form_members.get(form_key, []))
        return bool(clicked)

    def download_button(self, label: str, data: Any = None, **kw: Any) -> bool:
        self._check_width(kw)
        self.downloads.append({"label": label, "data": data, **kw})
        self._record("download_button", label)
        return False

    def _widget_kw(self, kw: dict[str, Any]) -> dict[str, Any]:
        allowed = {"on_change", "args", "kwargs"}
        return {k: v for k, v in kw.items() if k in allowed}

    def _check_width(self, kw: dict[str, Any]) -> None:
        """Reproduz a troca de `use_container_width` por `width` (Streamlit >= 1.50)."""
        modern = tuple(int(p) for p in self.__version__.split(".")[:2]) >= (1, 50)
        if modern and "use_container_width" in kw:
            raise TypeError("got an unexpected keyword argument 'use_container_width'")
        if not modern and kw.get("width") == "stretch":
            raise StreamlitAPIException("Invalid width value: 'stretch'")

    # --------------------------------------------------------------------- conteúdo
    def markdown(self, body: str, unsafe_allow_html: bool = False, **kw: Any) -> None:
        self._record("markdown", body, unsafe=unsafe_allow_html)

    def caption(self, body: str, **kw: Any) -> None:
        self._record("caption", body)

    def subheader(self, body: str, **kw: Any) -> None:
        self._record("subheader", body)

    def write(self, *body: Any, **kw: Any) -> None:
        self._record("write", " ".join(str(b) for b in body))

    def code(self, body: str, language: str | None = None, **kw: Any) -> None:
        self._record("code", body)

    def info(self, body: str, **kw: Any) -> None:
        self._record("info", body)

    def toast(self, body: str, **kw: Any) -> None:
        self._record("toast", body)

    def divider(self) -> None:
        self._record("divider")

    def image(self, source: Any, caption: str | None = None, **kw: Any) -> None:
        self._check_width(kw)
        self._record("image", str(source), caption=caption or "")

    def dataframe(self, data: Any, **kw: Any) -> None:
        self._check_width(kw)
        self.dataframes.append(data)
        self._record("dataframe", data.to_string(index=False))

    def bar_chart(self, data: Any, **kw: Any) -> None:
        self._record("bar_chart", data.to_string())

    def set_page_config(self, **kw: Any) -> None:
        self._record("page_config", kw.get("page_title", ""))

    def _iframe(self, source: str, **kw: Any) -> None:
        self._record("iframe", source)

    def rerun(self) -> None:
        raise RerunException

    # -------------------------------------------------------------------- estrutura
    def columns(self, spec: Any, **kw: Any) -> list[_Context]:
        count = spec if isinstance(spec, int) else len(spec)
        return [_Context(self, "column") for _ in range(count)]

    def tabs(self, labels: list[str]) -> list[_Context]:
        return [_Context(self, "tab", label) for label in labels]

    def container(self, **kw: Any) -> _Context:
        return _Context(self, "container")

    def expander(self, label: str, **kw: Any) -> _Context:
        return _Context(self, "expander", label)

    @contextmanager
    def form(self, key: str, clear_on_submit: bool = False, **kw: Any):  # type: ignore[no-untyped-def]
        self._form_stack.append((key, clear_on_submit))
        self._form_members.setdefault(key, [])
        try:
            yield self
        finally:
            self._form_stack.pop()

    @contextmanager
    def spinner(self, text: str = "") -> Any:
        yield self

    def dialog(self, title: str, **kw: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                self._record("dialog", title)
                return fn(*args, **kwargs)

            wrapper.__name__ = fn.__name__
            return wrapper

        return decorate

    def cache_resource(self, *dargs: Any, **dkw: Any) -> Any:
        def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
            store = self._cache.setdefault(fn, {})

            def wrapper(*args: Any) -> Any:
                if args not in store:
                    store[args] = fn(*args)
                return store[args]

            wrapper.clear = store.clear  # type: ignore[attr-defined]
            return wrapper

        if dargs and callable(dargs[0]):
            return decorate(dargs[0])
        return decorate
