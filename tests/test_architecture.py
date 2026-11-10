"""Separação em camadas (RNF05): interface → serviços → repositórios → banco."""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "mercadofacil"


def imported_modules(path: Path) -> set[str]:
    """Nomes completos dos módulos importados por um arquivo (relativos resolvidos)."""
    parts = list(path.relative_to(PACKAGE.parent).with_suffix("").parts)
    package = parts[:-1]
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - node.level + 1]
                module = ".".join([*base, *(node.module.split(".") if node.module else [])])
            else:
                module = node.module or ""
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def layer_files(layer: str) -> list[Path]:
    return sorted((PACKAGE / layer).rglob("*.py"))


def uses(path: Path, prefixes: tuple[str, ...]) -> list[str]:
    return sorted(
        m for m in imported_modules(path) if any(m == p or m.startswith(p + ".") for p in prefixes)
    )


def test_camadas_respeitam_a_direcao_das_dependencias() -> None:
    # repositórios: só falam com o banco e com modelos/utilitários
    for path in layer_files("repositories"):
        proibidos = uses(path, ("mercadofacil.services", "mercadofacil.ui", "streamlit"))
        assert not proibidos, f"{path.name}: {proibidos}"
    # serviços: não conhecem a interface nem o Streamlit
    for path in layer_files("services"):
        proibidos = uses(path, ("mercadofacil.ui", "streamlit"))
        assert not proibidos, f"{path.name}: {proibidos}"
    # interface: nunca acessa o SQL/repositórios diretamente; usa os serviços
    for path in layer_files("ui"):
        proibidos = uses(path, ("mercadofacil.repositories", "sqlite3.connect"))
        assert not proibidos, f"{path.name}: {proibidos}"


def test_nenhuma_funcao_de_servico_importa_a_interface() -> None:
    nucleo = [
        PACKAGE / name
        for name in ("config.py", "database.py", "models.py", "money.py", "validators.py")
    ]
    for path in [*nucleo, *layer_files("services"), *layer_files("repositories")]:
        assert not uses(path, ("mercadofacil.ui", "streamlit")), path.name


def test_somente_a_interface_conhece_o_streamlit() -> None:
    for path in PACKAGE.rglob("*.py"):
        if "ui" in path.relative_to(PACKAGE).parts:
            continue
        assert not uses(path, ("streamlit",)), path.name


def test_modulos_puros_da_interface_nao_dependem_do_streamlit() -> None:
    """Estes módulos são testados sem abrir a interface."""
    for name in ("cart", "formatting", "navigation", "theme", "docs_content", "ct_runner"):
        assert not uses(PACKAGE / "ui" / f"{name}.py", ("streamlit",)), name


def test_regras_nao_vivem_na_interface() -> None:
    """A interface não escreve SQL: ele fica nos repositórios e no esquema."""
    for path in layer_files("ui"):
        texto = path.read_text(encoding="utf-8").upper()
        for comando in ("INSERT INTO", "UPDATE ", "DELETE FROM", "SELECT "):
            assert comando not in texto.replace("SELECIONE", ""), (path.name, comando)
