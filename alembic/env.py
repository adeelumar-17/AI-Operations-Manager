'''
This file is part of the Alembic migration environment. It sets up the context for running migrations, either in 'offline' mode (where no database connection is required) or 'online' mode (where a database connection is established). The configuration is read from the Alembic .ini file, and logging is configured accordingly. The target metadata for autogeneration of migrations can be specified here, but it is currently set to None.

methods: run_migrations_offline() - Configures and runs migrations in offline mode.
         run_migrations_online() - Configures and runs migrations in online mode.
'''

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from backend.app.core.config import settings
from backend.app.db.models import Base

import backend.app.db.models
config = context.config
# Alembic migrations must connect directly to the database instance (unpooled)
# rather than through a connection pooler (such as Neon's PgBouncer) because DDL
# statements, migration locks, and transactional session states require direct connections.
migration_url = settings.DATABASE_URL_DIRECT or settings.DATABASE_URL

config.set_main_option(
    "sqlalchemy.url",
    migration_url,
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
