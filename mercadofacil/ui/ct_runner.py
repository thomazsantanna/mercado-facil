"""Executa os casos de teste CT01–CT12 (seção 8) e devolve o resultado de cada um.

Roda o `pytest` num processo separado, sobre um banco temporário criado pelos
próprios testes; nenhum dado do sistema em uso é tocado.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .. import config
from . import docs_content

_LINE = re.compile(
    r"^(?P<node>\S+::test_ct(?P<num>\d{2})_\S+)\s+(?P<outcome>PASSED|FAILED|ERROR|SKIPPED)"
)
TIMEOUT_SECONDS = 180


@dataclass(frozen=True)
class CaseRun:
    results: dict[str, str] = field(default_factory=dict)  # "CT01" -> "PASSED" | "FAILED" | ...
    output: str = ""
    error: str | None = None  # indisponibilidade do pytest, tempo esgotado etc.

    @property
    def all_passed(self) -> bool:
        return (
            self.error is None
            and len(self.results) == len(docs_content.TEST_CASES)
            and all(outcome == "PASSED" for outcome in self.results.values())
        )


def parse_results(output: str) -> dict[str, str]:
    """Extrai 'CTnn -> resultado' da saída verbosa do pytest."""
    results: dict[str, str] = {}
    for line in output.splitlines():
        match = _LINE.match(line.strip())
        if match:
            results[f"CT{match.group('num')}"] = match.group("outcome")
    return results


def run_case_tests(root: Path | None = None) -> CaseRun:
    base = root or config.BASE_DIR
    target = base / docs_content.CT_TEST_FILE
    if not target.exists():
        return CaseRun(error="Os arquivos de teste não estão nesta instalação.")
    command = [
        sys.executable,
        "-m",
        "pytest",
        docs_content.CT_TEST_FILE,
        "-o",
        "addopts=",  # o "-q" do pyproject anularia o "-v" e a saída não traria o nome dos testes
        "-v",
        "--tb=short",
        "--no-header",
        "-p",
        "no:cacheprovider",
    ]
    try:
        completed = subprocess.run(  # noqa: S603 - comando fixo, sem entrada do usuário
            command,
            cwd=base,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CaseRun(error="Os testes demoraram mais que o esperado e foram interrompidos.")
    except OSError as exc:
        return CaseRun(error=f"Não foi possível executar o pytest: {exc}")
    output = completed.stdout + completed.stderr
    if "No module named pytest" in output:
        return CaseRun(
            output=output,
            error="O pytest não está instalado. Instale com: pip install -r requirements-dev.txt",
        )
    return CaseRun(results=parse_results(output), output=output)
