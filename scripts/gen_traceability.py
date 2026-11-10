"""Gera docs/RASTREABILIDADE.md a partir de mercadofacil/ui/docs_content.py.

Uso (na raiz do projeto):  python scripts/gen_traceability.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mercadofacil.ui import traceability  # noqa: E402


def main() -> int:
    broken = traceability.problems()
    if broken:
        print("Referências quebradas:", *broken, sep="\n  - ")
        return 1
    target = ROOT / "docs" / "RASTREABILIDADE.md"
    target.parent.mkdir(exist_ok=True)
    target.write_text(traceability.render_markdown(), encoding="utf-8")
    print(f"Gerado: {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
