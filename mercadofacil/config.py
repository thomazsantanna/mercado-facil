"""Configurações do sistema.

Os valores que dependem do ambiente são lidos por funções (e não em tempo de
importação) para que os testes possam apontar para um banco temporário.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Mercado Fácil"

BASE_DIR = Path(__file__).resolve().parent.parent

# RB07 — percentual de cashback sobre o total líquido da venda.
CASHBACK_RATE_PERCENT = 1

# Hash de senhas (PBKDF2-HMAC-SHA256).
PBKDF2_ITERATIONS = 200_000

# Papéis aceitos pelo sistema (RNF08).
ROLE_OPERATOR = "operador"
ROLE_STOCKER = "estoquista"
ROLE_MANAGER = "gestor"
ROLES = (ROLE_OPERATOR, ROLE_STOCKER, ROLE_MANAGER)


def get_db_path() -> Path:
    """Caminho do arquivo SQLite (variável MERCADO_FACIL_DB)."""
    custom = os.environ.get("MERCADO_FACIL_DB")
    if custom:
        return Path(custom)
    return BASE_DIR / "data" / "mercado_facil.db"


def get_timezone() -> str:
    return os.environ.get("MERCADO_FACIL_TZ", "America/Sao_Paulo")


def seed_demo_data_enabled() -> bool:
    """Se falso, apenas os usuários iniciais são criados em base vazia."""
    return os.environ.get("MERCADO_FACIL_SEED", "1") != "0"


def show_demo_users() -> bool:
    """Exibe as credenciais de demonstração na tela de login."""
    return os.environ.get("MERCADO_FACIL_SHOW_DEMO_USERS", "1") != "0"
