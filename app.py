"""Ponto de entrada do Mercado Fácil.

Execute, a partir desta pasta:

    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:  # permite iniciar de qualquer diretório de trabalho
    sys.path.insert(0, str(ROOT))

from mercadofacil.ui import shell  # noqa: E402

shell.main()
