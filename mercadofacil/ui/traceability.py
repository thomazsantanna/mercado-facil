"""Matriz de rastreabilidade: requisito → código → teste, conferida contra os arquivos reais."""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path

from .. import config
from . import docs_content
from .docs_content import Requirement


@cache
def _names_in(path: Path) -> frozenset[str]:
    """Funções, classes e constantes definidas no arquivo (em qualquer nível).

    Em arquivos que não são Python (ex.: `pyproject.toml`), vale qualquer palavra do texto.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".py":
        return frozenset(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text))
    tree = ast.parse(text)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return frozenset(names)


def _split(ref: str, separator: str) -> tuple[str, str]:
    file, _, name = ref.rpartition(separator)
    return file, name


def check_code_ref(ref: str, root: Path | None = None) -> str | None:
    """None se `arquivo.py:nome` existe; senão, o motivo."""
    base = root or config.BASE_DIR
    file, name = _split(ref, ":")
    if not file or not name:
        return f"referência malformada: {ref}"
    path = base / file
    if not path.is_file():
        return f"arquivo não encontrado: {file}"
    if name not in _names_in(path):
        return f"{name!r} não está definido em {file}"
    return None


def check_test_ref(ref: str, root: Path | None = None) -> str | None:
    """None se `tests/arquivo.py::teste` existe; senão, o motivo."""
    base = root or config.BASE_DIR
    file, _, rest = ref.partition("::")
    name = rest.rpartition("::")[2]
    if not file or not name:
        return f"referência malformada: {ref}"
    path = base / file
    if not path.is_file():
        return f"arquivo não encontrado: {file}"
    if name not in _names_in(path):
        return f"teste {name!r} não existe em {file}"
    return None


def problems(root: Path | None = None) -> list[str]:
    """Todas as referências quebradas (lista vazia = matriz íntegra)."""
    found: list[str] = []
    for requirement in docs_content.ALL_REQUIREMENTS:
        if not requirement.code:
            found.append(f"{requirement.id}: sem implementação indicada")
        if not requirement.tests:
            found.append(f"{requirement.id}: sem teste indicado")
        for ref in requirement.code:
            if (reason := check_code_ref(ref, root)) is not None:
                found.append(f"{requirement.id}: {reason}")
        for ref in requirement.tests:
            if (reason := check_test_ref(ref, root)) is not None:
                found.append(f"{requirement.id}: {reason}")
    for case in docs_content.TEST_CASES:
        ref = f"{docs_content.CT_TEST_FILE}::{case.test}"
        if (reason := check_test_ref(ref, root)) is not None:
            found.append(f"{case.id}: {reason}")
    return found


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _table(title: str, requirements: tuple[Requirement, ...]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| ID | Requisito | Implementado em | Verificado por |",
        "|----|-----------|-----------------|----------------|",
    ]
    for r in requirements:
        code = "<br>".join(f"`{ref}`" for ref in r.code)
        tests = "<br>".join(f"`{ref}`" for ref in r.tests)
        lines.append(f"| {r.id} | {_cell(r.text)} | {code} | {tests} |")
    return [*lines, ""]


def render_markdown() -> str:
    """Conteúdo de docs/RASTREABILIDADE.md, gerado a partir de `docs_content`."""
    lines = [
        "# Rastreabilidade — Mercado Fácil",
        "",
        "> Arquivo gerado por `python scripts/gen_traceability.py`; não edite à mão.",
        "> `tests/test_traceability.py` confere que cada função e cada teste citado existe.",
        "",
        *_table("Requisitos funcionais (RF01–RF16)", docs_content.FUNCTIONAL),
        *_table("Requisitos não funcionais (RNF01–RNF11)", docs_content.NON_FUNCTIONAL),
        *_table("Regras de negócio (RB01–RB12)", docs_content.BUSINESS_RULES),
        "## Casos de teste (seção 8)",
        "",
        "| ID | Cenário | Resultado esperado | Teste automatizado |",
        "|----|---------|--------------------|--------------------|",
    ]
    for case in docs_content.TEST_CASES:
        lines.append(
            f"| {case.id} | {_cell(case.scenario)} | {_cell(case.expected)} | "
            f"`{docs_content.CT_TEST_FILE}::{case.test}` |"
        )
    return "\n".join(lines) + "\n"
