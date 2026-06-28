"""Postgres database base + engine factory."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

__all__ = [
    "Base",
    "create_engine_for_url",
    "session_factory",
]


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


def create_engine_for_url(
    database_url: str,
    *,
    echo: bool = False,
    pool_size: int = 5,
) -> Engine:
    """Build a sync SQLAlchemy engine (used by Alembic and the CLI migrate path)."""
    return create_engine(
        database_url,
        echo=echo,
        pool_size=pool_size,
        future=True,
    )


@contextmanager
def session_factory(engine: Engine) -> Iterator[Session]:
    """Yield a short-lived :class:`Session` (Alembic / admin scripts)."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


_ = Any  # silence unused-import warning on type-alias only
_ = logging  # type: ignore[misc]  # re-export for downstream adapters
