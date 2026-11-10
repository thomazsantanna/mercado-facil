"""Backup do banco (RNF10: backup e recuperação definidos antes do uso comercial)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from .. import clock
from ..models import User
from . import permissions


def backup_to_file(conn: sqlite3.Connection, destination: str | Path) -> Path:
    """Cópia consistente do banco (API de backup do SQLite) para `destination`."""
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    copy = sqlite3.connect(str(target))
    try:
        conn.backup(copy)
    finally:
        copy.close()
    return target


def backup_bytes(conn: sqlite3.Connection, actor: User) -> tuple[str, bytes]:
    """Gera o backup em memória para download. Retorna (nome do arquivo, conteúdo)."""
    permissions.ensure_permission(actor, permissions.BACKUP_RUN)
    with tempfile.TemporaryDirectory() as directory:
        path = backup_to_file(conn, Path(directory) / "backup.db")
        content = path.read_bytes()
    filename = f"mercado_facil_backup_{clock.now().strftime('%Y%m%d_%H%M%S')}.db"
    return filename, content
