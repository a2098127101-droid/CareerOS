from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.config import Settings
from app.core.database import BASELINE_METADATA, normalize_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = Settings()
configured_url = os.getenv("ALEMBIC_DATABASE_URL") or settings.database_url
url = normalize_database_url(configured_url, settings.db_path)
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
target_metadata = BASELINE_METADATA


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        if connection.dialect.name == "postgresql":
            # Alembic defaults version_num to VARCHAR(32), while CareerOS
            # intentionally uses descriptive revision identifiers longer than
            # 32 characters. SQLite does not enforce that length, so establish
            # the portable width explicitly before Alembic stamps a revision.
            connection.execute(text(
                "CREATE TABLE IF NOT EXISTS alembic_version ("
                "version_num VARCHAR(128) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
            ))
            connection.execute(text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(128)"
            ))
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
