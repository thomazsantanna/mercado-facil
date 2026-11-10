"""Inicialização do sistema: cria o esquema e, se a base estiver vazia, os dados de demonstração.

A interface chama `initialize()` uma única vez por processo. Cada operação abre
a sua própria conexão curta (`database.connect`), o que é barato no SQLite e
evita compartilhar conexões entre execuções da interface.
"""

from __future__ import annotations

from pathlib import Path

from . import config
from .database import connect, init_schema
from .seed import ensure_initial_data


def initialize(db_path: str | Path | None = None) -> Path:
    """Prepara o banco e devolve o caminho do arquivo em uso."""
    path = Path(db_path) if db_path is not None else config.get_db_path()
    with connect(path) as conn:
        init_schema(conn)
        ensure_initial_data(conn)
    return path
