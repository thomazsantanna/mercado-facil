"""Usuários do sistema."""

from __future__ import annotations

import sqlite3

from ..models import User, build, build_all


def get_user_row(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    return row


def get_user(conn: sqlite3.Connection, username: str) -> User | None:
    return build(User, get_user_row(conn, username))


def insert_user(
    conn: sqlite3.Connection, *, username: str, name: str, role: str, password_hash: str
) -> int:
    cursor = conn.execute(
        "INSERT INTO users (username, name, role, password_hash) VALUES (?, ?, ?, ?)",
        (username, name, role, password_hash),
    )
    return int(cursor.lastrowid or 0)


def update_password(conn: sqlite3.Connection, username: str, password_hash: str) -> None:
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))


def count_users(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def list_users(conn: sqlite3.Connection) -> list[User]:
    rows = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    return build_all(User, rows)
