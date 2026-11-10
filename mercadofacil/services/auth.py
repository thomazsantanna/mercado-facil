"""Autenticação com senhas protegidas por PBKDF2 (RNF08)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3

from .. import config
from ..config import ROLE_MANAGER, ROLES
from ..errors import AuthenticationError, PermissionDeniedError, ValidationError
from ..models import User, build
from ..repositories import users as users_repo
from ..validators import require_text

_ALGORITHM = "pbkdf2_sha256"
MIN_PASSWORD_LENGTH = 6
# Hash usado só para igualar o tempo de resposta quando o usuário não existe.
_DUMMY_HASH = f"{_ALGORITHM}${config.PBKDF2_ITERATIONS}${'00' * 16}${'00' * 32}"


def hash_password(
    password: str, *, salt: bytes | None = None, iterations: int | None = None
) -> str:
    rounds = iterations or config.PBKDF2_ITERATIONS
    salt_bytes = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, rounds)
    return f"{_ALGORITHM}${rounds}${salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_user(
    conn: sqlite3.Connection, *, username: str, name: str, role: str, password: str
) -> User:
    login = require_text(username, "o nome de usuário", max_length=40).lower()
    if " " in login:
        raise ValidationError("O nome de usuário não pode conter espaços.")
    full_name = require_text(name, "o nome do usuário", max_length=80)
    if role not in ROLES:
        raise ValidationError("Perfil inválido.")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"A senha deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres.")
    if users_repo.get_user_row(conn, login) is not None:
        raise ValidationError(f"O usuário “{login}” já existe.")
    users_repo.insert_user(
        conn, username=login, name=full_name, role=role, password_hash=hash_password(password)
    )
    user = users_repo.get_user(conn, login)
    assert user is not None
    return user


def authenticate(conn: sqlite3.Connection, username: str, password: str) -> User:
    """Valida credenciais; a mensagem de erro não revela qual campo falhou."""
    row = users_repo.get_user_row(conn, (username or "").strip().lower())
    stored = row["password_hash"] if row is not None else _DUMMY_HASH
    password_ok = verify_password(password or "", stored)
    if row is None or not password_ok or not row["active"]:
        raise AuthenticationError("Usuário ou senha inválidos.")
    user = build(User, row)
    assert user is not None
    return user


def reload_user(conn: sqlite3.Connection, username: str) -> User | None:
    """Usuário atualizado a partir do banco; `None` se não existe ou foi desativado."""
    user = users_repo.get_user(conn, (username or "").strip().lower())
    return user if user is not None and user.active else None


def authorize_manager(conn: sqlite3.Connection, username: str, password: str) -> User:
    """Autorização de gestor para pós-venda (supervisor override)."""
    try:
        manager = authenticate(conn, username, password)
    except AuthenticationError:
        raise AuthenticationError(
            "Autorização negada: usuário ou senha do gestor inválidos."
        ) from None
    if manager.role != ROLE_MANAGER:
        raise PermissionDeniedError("Autorização negada: somente um gestor pode autorizar.")
    return manager


def change_password(conn: sqlite3.Connection, user: User, current: str, new: str) -> None:
    authenticate(conn, user.username, current)
    if len(new or "") < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"A nova senha deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres.")
    users_repo.update_password(conn, user.username, hash_password(new))
