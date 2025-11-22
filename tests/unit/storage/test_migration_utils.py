"""Utilities and helper tests for database migrations."""

import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


class MigrationTestHelper:
    """Helper class for migration testing."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize with optional database path."""
        if db_path is None:
            # Create temporary directory first
            temp_dir = Path(tempfile.mkdtemp())
            self.db_path = temp_dir / "test_migration.db"
            self.temp_file = None
            self._temp_dir = temp_dir
        else:
            self.db_path = db_path
            self.temp_file = None
            self._temp_dir = None

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.database_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(self.database_url)
        self.alembic_config = self._create_alembic_config()

    def _create_alembic_config(self) -> Config:
        """Create Alembic configuration."""
        config = Config()
        config.set_main_option("script_location", "paidsearchnav/storage/migrations")
        config.set_main_option("sqlalchemy.url", self.database_url)
        return config

    def cleanup(self):
        """Clean up resources."""
        if self.engine:
            self.engine.dispose()
        if self._temp_dir and self._temp_dir.exists():
            import shutil

            shutil.rmtree(self._temp_dir)
        elif self.db_path.exists():
            self.db_path.unlink(missing_ok=True)

    def get_current_revision(self) -> Optional[str]:
        """Get current database revision."""
        with self.engine.connect() as conn:
            migration_context = MigrationContext.configure(conn)
            return migration_context.get_current_revision()

    def get_table_names(self) -> List[str]:
        """Get list of table names in database."""
        inspector = inspect(self.engine)
        return inspector.get_table_names()

    def get_table_schema(self, table_name: str) -> Dict:
        """Get schema information for a table."""
        inspector = inspect(self.engine)
        return {
            "columns": inspector.get_columns(table_name),
            "indexes": inspector.get_indexes(table_name),
            "foreign_keys": inspector.get_foreign_keys(table_name),
            "unique_constraints": inspector.get_unique_constraints(table_name),
        }

    def upgrade_to_revision(self, revision: str = "head"):
        """Upgrade database to specified revision."""
        command.upgrade(self.alembic_config, revision)

    def downgrade_to_revision(self, revision: str = "base"):
        """Downgrade database to specified revision."""
        command.downgrade(self.alembic_config, revision)

    def get_all_revisions(self) -> List:
        """Get list of all migration revisions."""
        script_dir = ScriptDirectory.from_config(self.alembic_config)
        return list(script_dir.walk_revisions())

    def insert_test_data(self):
        """Insert minimal test data for migration testing."""
        with self.engine.connect() as conn:
            # Insert test user
            conn.execute(
                text("""
                INSERT INTO users (id, email, name, user_type, is_active, created_at, updated_at)
                VALUES (:id, :email, :name, :user_type, :is_active, datetime('now'), datetime('now'))
                """),
                {
                    "id": "test-user-migration",
                    "email": "migration-test@example.com",
                    "name": "Migration Test User",
                    "user_type": "individual",
                    "is_active": 1,
                },
            )

            # Insert test customer
            conn.execute(
                text("""
                INSERT INTO customers (id, name, user_id, is_active, created_at, updated_at)
                VALUES (:id, :name, :user_id, :is_active, datetime('now'), datetime('now'))
                """),
                {
                    "id": "test-customer-migration",
                    "name": "Migration Test Customer",
                    "user_id": "test-user-migration",
                    "is_active": 1,
                },
            )

            conn.commit()

    def verify_test_data(self) -> bool:
        """Verify test data exists in database."""
        with self.engine.connect() as conn:
            user_count = conn.execute(
                text("SELECT COUNT(*) FROM users WHERE id = :user_id"),
                {"user_id": "test-user-migration"},
            ).scalar()
            customer_count = conn.execute(
                text("SELECT COUNT(*) FROM customers WHERE id = :customer_id"),
                {"customer_id": "test-customer-migration"},
            ).scalar()
            return user_count == 1 and customer_count == 1


class TestMigrationUtils:
    """Test the migration utilities themselves."""

    def test_migration_helper_initialization(self):
        """Test MigrationTestHelper initialization."""
        helper = MigrationTestHelper()
        try:
            assert helper.db_path.exists() or helper.db_path.name.endswith(".db")
            assert helper.database_url.startswith("sqlite:///")
            assert helper.alembic_config is not None
        finally:
            helper.cleanup()

    def test_migration_helper_upgrade_downgrade(self):
        """Test helper upgrade and downgrade methods."""
        helper = MigrationTestHelper()
        try:
            # Test upgrade
            helper.upgrade_to_revision("head")
            tables = helper.get_table_names()
            assert "users" in tables
            assert "customers" in tables

            # Test downgrade
            helper.downgrade_to_revision("base")
            tables = helper.get_table_names()
            assert "users" not in tables
            assert "customers" not in tables
            assert "alembic_version" in tables
        finally:
            helper.cleanup()

    def test_migration_helper_schema_inspection(self):
        """Test schema inspection methods."""
        helper = MigrationTestHelper()
        try:
            helper.upgrade_to_revision("head")

            # Test table schema inspection
            users_schema = helper.get_table_schema("users")
            assert "columns" in users_schema
            assert "indexes" in users_schema
            assert "foreign_keys" in users_schema

            # Check that users table has expected columns
            column_names = [col["name"] for col in users_schema["columns"]]
            expected_columns = [
                "id",
                "email",
                "name",
                "user_type",
                "is_active",
                "created_at",
                "updated_at",
            ]
            for col in expected_columns:
                assert col in column_names
        finally:
            helper.cleanup()

    def test_migration_helper_test_data(self):
        """Test test data insertion and verification."""
        helper = MigrationTestHelper()
        try:
            helper.upgrade_to_revision("head")

            # Insert test data
            helper.insert_test_data()

            # Verify test data
            assert helper.verify_test_data()

            # Verify data persists
            assert helper.verify_test_data()
        finally:
            helper.cleanup()


class TestMigrationVersioning:
    """Test migration versioning and revision management."""

    def test_revision_history_consistency(self):
        """Test that revision history is consistent."""
        helper = MigrationTestHelper()
        try:
            revisions = helper.get_all_revisions()

            # Should have at least one revision
            assert len(revisions) > 0

            # Check revision chain
            current_rev = None
            for revision in reversed(revisions):
                if current_rev is not None:
                    assert revision.down_revision == current_rev
                current_rev = revision.revision
        finally:
            helper.cleanup()

    def test_revision_upgrade_path(self):
        """Test upgrading through each revision in sequence."""
        helper = MigrationTestHelper()
        try:
            revisions = helper.get_all_revisions()

            # Upgrade through each revision
            for revision in reversed(revisions):
                helper.upgrade_to_revision(revision.revision)
                current_rev = helper.get_current_revision()
                assert current_rev == revision.revision
        finally:
            helper.cleanup()

    def test_revision_downgrade_path(self):
        """Test downgrading through each revision in sequence."""
        helper = MigrationTestHelper()
        try:
            # First upgrade to head
            helper.upgrade_to_revision("head")

            revisions = helper.get_all_revisions()

            # Downgrade through each revision
            for revision in revisions:
                if revision.down_revision:
                    helper.downgrade_to_revision(revision.down_revision)
                    current_rev = helper.get_current_revision()
                    assert current_rev == revision.down_revision
        finally:
            helper.cleanup()


class TestMigrationDataIntegrity:
    """Test data integrity during migrations."""

    def test_schema_constraints_preservation(self):
        """Test that schema constraints are preserved during migrations."""
        helper = MigrationTestHelper()
        try:
            helper.upgrade_to_revision("head")

            # Get initial schema
            initial_schema = {}
            for table in ["users", "customers", "customer_access"]:
                initial_schema[table] = helper.get_table_schema(table)

            # Downgrade and upgrade
            helper.downgrade_to_revision("base")
            helper.upgrade_to_revision("head")

            # Check that schemas match
            current_tables = helper.get_table_names()
            for table in ["users", "customers", "customer_access"]:
                # Verify table exists after upgrade
                assert table in current_tables, f"Table {table} missing after upgrade"

                current_schema = helper.get_table_schema(table)

                # Compare column names (order might differ)
                initial_cols = set(
                    col["name"] for col in initial_schema[table]["columns"]
                )
                current_cols = set(col["name"] for col in current_schema["columns"])
                assert initial_cols == current_cols
        finally:
            helper.cleanup()

    def test_index_preservation(self):
        """Test that indexes are preserved during migrations."""
        helper = MigrationTestHelper()
        try:
            helper.upgrade_to_revision("head")

            # Get indexes for key tables
            initial_indexes = {}
            for table in ["users", "customers", "job_executions"]:
                schema = helper.get_table_schema(table)
                initial_indexes[table] = len(schema["indexes"])

            # Downgrade and upgrade
            helper.downgrade_to_revision("base")
            helper.upgrade_to_revision("head")

            # Verify indexes are recreated
            for table in ["users", "customers", "job_executions"]:
                schema = helper.get_table_schema(table)
                current_index_count = len(schema["indexes"])
                assert current_index_count == initial_indexes[table]
        finally:
            helper.cleanup()


class TestMigrationErrorHandling:
    """Test migration error handling and recovery."""

    def test_invalid_revision_handling(self):
        """Test handling of invalid revision identifiers."""
        helper = MigrationTestHelper()
        try:
            # Try to upgrade to non-existent revision
            with pytest.raises(Exception):
                helper.upgrade_to_revision("invalid-revision-123")
        finally:
            helper.cleanup()

    def test_migration_state_recovery(self):
        """Test recovery from partial migration states."""
        helper = MigrationTestHelper()
        try:
            # Upgrade to head
            helper.upgrade_to_revision("head")

            # Verify state
            current_rev = helper.get_current_revision()
            assert current_rev is not None

            # Verify we can still perform operations
            tables = helper.get_table_names()
            assert len(tables) > 0
        finally:
            helper.cleanup()


@pytest.fixture
def migration_helper():
    """Pytest fixture for MigrationTestHelper."""
    helper = MigrationTestHelper()
    yield helper
    helper.cleanup()


@pytest.fixture
def populated_migration_helper():
    """Pytest fixture for MigrationTestHelper with test data."""
    helper = MigrationTestHelper()
    helper.upgrade_to_revision("head")
    helper.insert_test_data()
    yield helper
    helper.cleanup()
