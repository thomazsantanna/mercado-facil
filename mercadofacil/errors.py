"""Erros do domínio. As mensagens são sempre apresentáveis ao usuário (RNF06)."""

from __future__ import annotations


class MercadoFacilError(Exception):
    """Erro base do sistema."""


class ValidationError(MercadoFacilError):
    """Dado de entrada ausente ou inválido."""


class BusinessRuleError(MercadoFacilError):
    """Violação de regra de negócio. `rule` guarda o ID (ex.: 'RB03')."""

    def __init__(self, message: str, rule: str | None = None):
        super().__init__(message)
        self.rule = rule


class NotFoundError(MercadoFacilError):
    """Registro inexistente."""


class PermissionDeniedError(MercadoFacilError):
    """O perfil do usuário não permite a operação (RNF08)."""


class AuthenticationError(MercadoFacilError):
    """Usuário ou senha inválidos."""
