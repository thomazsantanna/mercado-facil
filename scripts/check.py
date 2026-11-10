"""Verificação completa do projeto: estilo, tipos, compilação e testes.

Uso (na raiz do projeto):  python scripts/check.py
Requer as dependências de desenvolvimento:  pip install -r requirements-dev.txt
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tool(name: str) -> list[str]:
    """Comando de uma ferramenta: como módulo do Python atual ou, na falta, o executável do PATH."""
    if importlib.util.find_spec(name) is not None:
        return [sys.executable, "-m", name]
    return [shutil.which(name) or name]


STEPS: list[tuple[str, list[str]]] = [
    ("Formatação (ruff format --check)", [*tool("ruff"), "format", "--check", "."]),
    ("Estilo e boas práticas (ruff check)", [*tool("ruff"), "check", "."]),
    ("Tipos (mypy --strict)", tool("mypy")),
    ("Compilação", [sys.executable, "-m", "compileall", "-q", "mercadofacil", "scripts", "app.py"]),
    ("Rastreabilidade", [sys.executable, "scripts/gen_traceability.py"]),
    ("Testes (pytest)", [*tool("pytest")]),
]


def main() -> int:
    failed: list[str] = []
    for title, command in STEPS:
        print(f"\n=== {title} ===", flush=True)
        try:
            completed = subprocess.run(command, cwd=ROOT, check=False)  # noqa: S603 - comandos fixos
            code = completed.returncode
        except OSError as exc:
            print(f"Não foi possível executar {command[0]}: {exc}")
            code = 1
        if code != 0:
            failed.append(title)
    print("\n" + "=" * 60)
    if failed:
        print("FALHOU:", *failed, sep="\n  - ")
        return 1
    print("Tudo certo: formatação, estilo, tipos, compilação, rastreabilidade e testes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
