"""Shared fixtures for storage tests."""

import tempfile
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from paidsearchnav.storage.models import Base


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "test_migration.db"
    yield db_path
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_engine(temp_db_path):
    """Create a test database engine."""
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def alembic_config(temp_db_path):
    """Create Alembic configuration for testing."""
    config = Config()
    config.set_main_option("script_location", "paidsearchnav/storage/migrations")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{temp_db_path}")
    return config


@pytest.fixture
def session(test_engine):
    """Create a database session for testing."""
    # Create all tables
    Base.metadata.create_all(test_engine)

    # Create session factory
    SessionLocal = sessionmaker(bind=test_engine)

    # Create session
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(test_engine)
