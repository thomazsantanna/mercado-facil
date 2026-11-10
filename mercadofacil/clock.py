"""Relógio do sistema (isolado para facilitar testes)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import config

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"


def now() -> datetime:
    """Data e hora local (sem fuso), com precisão de segundos."""
    try:
        current = datetime.now(ZoneInfo(config.get_timezone()))
        return current.replace(tzinfo=None, microsecond=0)
    except ZoneInfoNotFoundError:
        return datetime.now().replace(microsecond=0)


def now_iso() -> str:
    return now().strftime(DATETIME_FORMAT)


def today() -> date:
    return now().date()


def today_iso() -> str:
    return today().strftime(DATE_FORMAT)


def days_ago_iso(days: int) -> str:
    return (today() - timedelta(days=days)).strftime(DATE_FORMAT)


def format_datetime(value: str | None) -> str:
    """'2026-10-27 18:05:00' -> '27/10/2026 18:05'."""
    if not value:
        return "—"
    try:
        return datetime.strptime(value, DATETIME_FORMAT).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def format_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.strptime(value[:10], DATE_FORMAT).strftime("%d/%m/%Y")
    except ValueError:
        return value
