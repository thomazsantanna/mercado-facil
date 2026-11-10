"""Acesso protegido e permissões por perfil (RNF08)."""

from __future__ import annotations

import sqlite3

import pytest

from mercadofacil.errors import AuthenticationError, PermissionDeniedError, ValidationError
from mercadofacil.services import auth, catalog, permissions, sales
from tests.conftest import PASSWORDS, World


def test_senha_nunca_fica_em_texto_puro(world: World) -> None:
    row = world.conn.execute("SELECT password_hash FROM users WHERE username = 'gestor'").fetchone()
    stored = row["password_hash"]
    assert PASSWORDS["gestor"] not in stored
    assert stored.startswith("pbkdf2_sha256$")


def test_hash_usa_sal_aleatorio() -> None:
    assert auth.hash_password("segredo1") != auth.hash_password("segredo1")


def test_autenticacao_correta(world: World) -> None:
    user = auth.authenticate(world.conn, " Gestor ", PASSWORDS["gestor"])
    assert user.username == "gestor"
    assert user.role == "gestor"
    assert user.role_label == "Gestor"


@pytest.mark.parametrize(
    ("username", "password"), [("gestor", "errada"), ("fantasma", "x"), ("", "")]
)
def test_autenticacao_invalida_nao_revela_qual_campo_falhou(
    world: World, username: str, password: str
) -> None:
    with pytest.raises(AuthenticationError, match="Usuário ou senha inválidos"):
        auth.authenticate(world.conn, username, password)


def test_usuario_inativo_nao_entra(world: World) -> None:
    world.conn.execute("UPDATE users SET active = 0 WHERE username = 'operador'")
    with pytest.raises(AuthenticationError):
        auth.authenticate(world.conn, "operador", PASSWORDS["operador"])


def test_verify_password_com_hash_corrompido() -> None:
    assert not auth.verify_password("x", "lixo")
    assert not auth.verify_password("x", "md5$1$00$00")


def test_criar_usuario_valida_dados(world: World) -> None:
    with pytest.raises(ValidationError, match="já existe"):
        auth.create_user(world.conn, username="gestor", name="X", role="gestor", password="123456")
    with pytest.raises(ValidationError, match="espaços"):
        auth.create_user(world.conn, username="a b", name="X", role="gestor", password="123456")
    with pytest.raises(ValidationError, match="Perfil inválido"):
        auth.create_user(world.conn, username="novo", name="X", role="root", password="123456")
    with pytest.raises(ValidationError, match="ao menos"):
        auth.create_user(world.conn, username="novo", name="X", role="gestor", password="123")


def test_trocar_senha(world: World) -> None:
    auth.change_password(world.conn, world.operator, PASSWORDS["operador"], "nova-senha")
    assert auth.authenticate(world.conn, "operador", "nova-senha").username == "operador"
    with pytest.raises(AuthenticationError):
        auth.authenticate(world.conn, "operador", PASSWORDS["operador"])
    with pytest.raises(AuthenticationError):
        auth.change_password(world.conn, world.operator, "errada", "outra-senha")
    with pytest.raises(ValidationError):
        auth.change_password(world.conn, world.operator, "nova-senha", "123")


def test_autorizacao_de_gestor(world: World) -> None:
    assert auth.authorize_manager(world.conn, "gestor", PASSWORDS["gestor"]).role == "gestor"
    with pytest.raises(AuthenticationError, match="Autorização negada"):
        auth.authorize_manager(world.conn, "gestor", "errada")
    with pytest.raises(PermissionDeniedError, match="somente um gestor"):
        auth.authorize_manager(world.conn, "operador", PASSWORDS["operador"])


def test_matriz_de_permissoes(world: World) -> None:
    op, st, ge = world.operator, world.stocker, world.manager
    assert permissions.can(op, permissions.SALE_CREATE)
    assert not permissions.can(op, permissions.PRODUCT_MANAGE)
    assert not permissions.can(op, permissions.STOCK_MOVE)
    assert permissions.can(st, permissions.STOCK_MOVE)
    assert not permissions.can(st, permissions.SALE_CREATE)
    assert not permissions.can(st, permissions.POSTSALE_REGISTER)
    assert all(permissions.can(ge, action) for action in permissions.ROLE_ACTIONS["gestor"])
    assert permissions.can(ge, permissions.BACKUP_RUN)
    assert not permissions.can(op, permissions.BACKUP_RUN)
    assert not permissions.can(None, permissions.DASHBOARD_VIEW)


def test_servidor_barra_acao_fora_do_perfil(world: World) -> None:
    """RNF03/RNF08: a regra vale no servidor, mesmo que a interface esconda o botão."""
    with pytest.raises(PermissionDeniedError, match="Operador de caixa"):
        catalog.create_product(
            world.conn, world.operator, barcode="1234567890123", name="Pirata", price_cents=100
        )
    world.open_cash()
    product = world.product()
    with pytest.raises(PermissionDeniedError, match="Estoquista"):
        sales.finalize_sale(world.conn, world.stocker, [(product.id, 1)], payment_method="pix")


def test_usuario_inativo_perde_as_permissoes(world: World, conn: sqlite3.Connection) -> None:
    from dataclasses import replace

    inactive = replace(world.operator, active=0)
    assert not permissions.can(inactive, permissions.SALE_CREATE)
    with pytest.raises(PermissionDeniedError):
        permissions.ensure_permission(None, permissions.SALE_CREATE)


def test_recarregar_usuario_devolve_somente_contas_ativas(world: World) -> None:
    reloaded = auth.reload_user(world.conn, " Operador ")
    assert reloaded is not None and reloaded.role == "operador"
    assert auth.reload_user(world.conn, "ninguem") is None
    world.conn.execute("UPDATE users SET active = 0 WHERE username = 'operador'")
    assert auth.reload_user(world.conn, "operador") is None
