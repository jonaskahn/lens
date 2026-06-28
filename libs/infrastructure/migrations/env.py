"""Alembic environment script.

Reads ``DATABASE_URL`` from the environment; falls back to the URL baked into
``alembic.ini``. Uses SQLAlchemy metadata from :mod:`lens_infrastructure.db.base`.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from dotenv import dotenv_values
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from lens_infrastructure.db import models  # noqa: F401 - ensure models are imported
from lens_infrastructure.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

db_url = dotenv_values().get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if db_url is None:
    raise RuntimeError("no database url configured")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(db_url, poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
