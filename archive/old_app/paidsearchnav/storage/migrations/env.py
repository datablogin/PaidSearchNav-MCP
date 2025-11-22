"""Alembic environment configuration."""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from paidsearchnav.core.config import Settings
from paidsearchnav.storage.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Get database URL from settings."""
    settings = Settings()

    if settings.environment == "production":
        # Use PostgreSQL in production
        if settings.database_url:
            url = settings.database_url.get_secret_value()
        else:
            host = os.getenv("PSN_DB_HOST", "localhost")
            port = os.getenv("PSN_DB_PORT", "5432")
            user = os.getenv("PSN_DB_USER", "paidsearchnav")
            password = os.getenv("PSN_DB_PASSWORD", "")
            database = os.getenv("PSN_DB_NAME", "paidsearchnav")

            if password:
                url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
            else:
                url = f"postgresql://{user}@{host}:{port}/{database}"

        # Convert PostgreSQL URL to use pg8000 driver instead of psycopg2
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+pg8000://")
        return url
    else:
        # Use SQLite for development
        db_path = settings.data_dir / "paidsearchnav.db"
        return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section)
    # Use URL from config if set (e.g., for testing), otherwise use Settings
    # However, always prefer environment-based URL when explicitly set
    existing_url = configuration.get("sqlalchemy.url")
    settings_url = get_url()

    # Use settings URL if it's different from the default SQLite URL in alembic.ini
    # or if no URL is configured
    if not existing_url or existing_url.startswith("sqlite:///data/"):
        final_url = settings_url
    else:
        final_url = existing_url

    # Convert PostgreSQL URL to use pg8000 driver instead of psycopg2
    if final_url and final_url.startswith("postgresql://"):
        final_url = final_url.replace("postgresql://", "postgresql+pg8000://")

    configuration["sqlalchemy.url"] = final_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
