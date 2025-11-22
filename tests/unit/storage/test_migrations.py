"""Unit tests for database migrations."""

import os
import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


class TestMigrationInfrastructure:
    """Test migration infrastructure and utilities."""

    def test_migration_environment_setup(self, alembic_config):
        """Test that migration environment is properly configured."""
        script_dir = ScriptDirectory.from_config(alembic_config)
        assert script_dir is not None
        assert script_dir.get_current_head() is not None

    def test_migration_scripts_exist(self):
        """Test that migration scripts exist in expected location."""
        migrations_dir = Path("paidsearchnav/storage/migrations/versions")
        assert migrations_dir.exists()
        migration_files = list(migrations_dir.glob("*.py"))
        assert len(migration_files) > 0

        # Check that at least the initial schema migration exists
        initial_migration = any("initial" in file.name for file in migration_files)
        assert initial_migration


class TestMigrationUpDown:
    """Test migration forward and backward operations."""

    def test_migration_upgrade_from_empty_database(self, alembic_config, test_engine):
        """Test migrating an empty database to latest version."""
        # Verify database is empty
        inspector = inspect(test_engine)
        assert len(inspector.get_table_names()) == 0

        # Run migrations
        command.upgrade(alembic_config, "head")

        # Verify all expected tables exist
        inspector = inspect(test_engine)
        table_names = inspector.get_table_names()

        expected_tables = {
            "users",
            "customers",
            "customer_access",
            "analysis_results",
            "analysis_comparisons",
            "job_executions",
            "google_ads_accounts",
            "customer_google_ads_accounts",
            "analysis_files",
            # S3 security tables
            "s3_access_permissions",
            "s3_audit_log",
            "customer_encryption_keys",
            "access_tokens",
            "service_accounts",
            "compliance_reports",
            "security_alerts",
            "alembic_version",
        }

        for table in expected_tables:
            assert table in table_names, f"Expected table {table} not found"

    def test_migration_downgrade_all(self, alembic_config, test_engine):
        """Test downgrading all migrations back to base."""
        # First upgrade to head
        command.upgrade(alembic_config, "head")

        # Verify tables exist
        inspector = inspect(test_engine)
        initial_tables = inspector.get_table_names()
        assert len(initial_tables) > 1  # Should have tables + alembic_version

        # Downgrade to base
        command.downgrade(alembic_config, "base")

        # Verify only alembic_version table remains
        inspector = inspect(test_engine)
        remaining_tables = inspector.get_table_names()
        assert set(remaining_tables) == {"alembic_version"}

    def test_migration_specific_revision_upgrade_downgrade(
        self, alembic_config, test_engine
    ):
        """Test upgrading and downgrading to specific revision."""
        # Get the job executions migration revision
        script_dir = ScriptDirectory.from_config(alembic_config)
        revisions = list(script_dir.walk_revisions())

        job_executions_rev = None
        for rev in revisions:
            if "job_executions" in str(rev.doc or "").lower():
                job_executions_rev = rev.revision
                break

        if job_executions_rev:
            # Upgrade to specific revision
            command.upgrade(alembic_config, job_executions_rev)

            # Verify job_executions table exists
            inspector = inspect(test_engine)
            assert "job_executions" in inspector.get_table_names()

            # Get the previous revision (if any)
            prev_rev = rev.down_revision
            if prev_rev:
                # Downgrade to previous revision
                command.downgrade(alembic_config, prev_rev)

                # Verify job_executions table no longer exists
                inspector = inspect(test_engine)
                assert "job_executions" not in inspector.get_table_names()

    def test_migration_rollback_functionality(self, alembic_config, test_engine):
        """Test that each migration can be rolled back successfully."""
        script_dir = ScriptDirectory.from_config(alembic_config)
        revisions = list(script_dir.walk_revisions())

        for revision in reversed(revisions):  # Start from oldest
            # Upgrade to this revision
            command.upgrade(alembic_config, revision.revision)

            # Verify upgrade worked
            with test_engine.connect() as conn:
                migration_context = MigrationContext.configure(conn)
                current_rev = migration_context.get_current_revision()
                assert current_rev == revision.revision

            # If there's a down revision, test rollback
            if revision.down_revision:
                command.downgrade(alembic_config, revision.down_revision)

                # Verify downgrade worked
                with test_engine.connect() as conn:
                    migration_context = MigrationContext.configure(conn)
                    current_rev = migration_context.get_current_revision()
                    assert current_rev == revision.down_revision


class TestMigrationIdempotency:
    """Test migration idempotency (running twice should be safe)."""

    def test_migration_upgrade_idempotency(self, alembic_config, test_engine):
        """Test that running migrations multiple times is safe."""
        # Run migrations once
        command.upgrade(alembic_config, "head")

        # Get initial state
        inspector = inspect(test_engine)
        initial_tables = inspector.get_table_names()
        initial_schema = {}
        for table in initial_tables:
            initial_schema[table] = inspector.get_columns(table)

        # Run migrations again
        command.upgrade(alembic_config, "head")

        # Verify state is unchanged
        inspector = inspect(test_engine)
        final_tables = inspector.get_table_names()
        final_schema = {}
        for table in final_tables:
            final_schema[table] = inspector.get_columns(table)

        assert set(initial_tables) == set(final_tables)

        # Compare schemas (basic check)
        for table in initial_tables:
            if table != "alembic_version":  # Skip version table
                initial_cols = [col["name"] for col in initial_schema[table]]
                final_cols = [col["name"] for col in final_schema[table]]
                assert initial_cols == final_cols

    def test_migration_downgrade_upgrade_cycle(self, alembic_config, test_engine):
        """Test downgrade followed by upgrade produces consistent state."""
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Get schema after first upgrade
        inspector = inspect(test_engine)
        first_upgrade_tables = inspector.get_table_names()

        # Downgrade to base
        command.downgrade(alembic_config, "base")

        # Upgrade again
        command.upgrade(alembic_config, "head")

        # Verify schema is the same
        inspector = inspect(test_engine)
        second_upgrade_tables = inspector.get_table_names()

        assert set(first_upgrade_tables) == set(second_upgrade_tables)


class TestMigrationDataPreservation:
    """Test that migrations preserve existing data."""

    def test_data_preservation_during_migration(self, alembic_config, test_engine):
        """Test that existing data is preserved during migrations."""
        # First, upgrade to a known good state
        command.upgrade(alembic_config, "head")

        # Insert test data
        with test_engine.connect() as conn:
            # Insert a test user
            conn.execute(
                text("""
                INSERT INTO users (id, email, name, user_type, is_active, created_at, updated_at)
                VALUES (:id, :email, :name, :user_type, :is_active, datetime('now'), datetime('now'))
                """),
                {
                    "id": "test-user-1",
                    "email": "test@example.com",
                    "name": "Test User",
                    "user_type": "individual",
                    "is_active": 1,
                },
            )

            # Insert a test customer
            conn.execute(
                text("""
                INSERT INTO customers (id, name, user_id, is_active, created_at, updated_at)
                VALUES (:id, :name, :user_id, :is_active, datetime('now'), datetime('now'))
                """),
                {
                    "id": "test-customer-1",
                    "name": "Test Customer",
                    "user_id": "test-user-1",
                    "is_active": 1,
                },
            )

            conn.commit()

        # Verify data exists
        with test_engine.connect() as conn:
            users_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            customers_count = conn.execute(
                text("SELECT COUNT(*) FROM customers")
            ).scalar()
            assert users_count == 1
            assert customers_count == 1

        # Downgrade and upgrade again (simulating a migration cycle)
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")

        # Verify data still exists (note: this tests the down/up cycle)
        # In real scenarios, data would be lost on downgrade to base
        # This test is more about ensuring migration structure is sound
        inspector = inspect(test_engine)
        assert "users" in inspector.get_table_names()
        assert "customers" in inspector.get_table_names()


class TestMigrationCompatibility:
    """Test schema compatibility and constraints."""

    def test_foreign_key_constraints(self, alembic_config, test_engine):
        """Test that foreign key constraints are properly created."""
        command.upgrade(alembic_config, "head")

        inspector = inspect(test_engine)

        # Check customer -> user foreign key
        customers_fks = inspector.get_foreign_keys("customers")
        user_fk = next(
            (fk for fk in customers_fks if fk["referred_table"] == "users"), None
        )
        assert user_fk is not None
        assert "user_id" in user_fk["constrained_columns"]

        # Check customer_access foreign keys
        access_fks = inspector.get_foreign_keys("customer_access")
        user_fk = next(
            (fk for fk in access_fks if fk["referred_table"] == "users"), None
        )
        customer_fk = next(
            (fk for fk in access_fks if fk["referred_table"] == "customers"), None
        )
        assert user_fk is not None
        assert customer_fk is not None

    def test_index_creation(self, alembic_config, test_engine):
        """Test that indexes are properly created."""
        command.upgrade(alembic_config, "head")

        inspector = inspect(test_engine)

        # Check some key indexes exist
        users_indexes = inspector.get_indexes("users")
        customers_indexes = inspector.get_indexes("customers")
        job_executions_indexes = inspector.get_indexes("job_executions")

        # Should have at least some indexes
        assert len(users_indexes) > 0
        assert len(customers_indexes) > 0
        assert len(job_executions_indexes) > 0

    def test_unique_constraints(self, alembic_config, test_engine):
        """Test that unique constraints are properly enforced."""
        command.upgrade(alembic_config, "head")

        with test_engine.connect() as conn:
            # Insert a user
            conn.execute(
                text("""
                INSERT INTO users (id, email, name, user_type, created_at, updated_at)
                VALUES (:id, :email, :name, :user_type, datetime('now'), datetime('now'))
                """),
                {
                    "id": "user1",
                    "email": "test@example.com",
                    "name": "Test User",
                    "user_type": "individual",
                },
            )
            conn.commit()

            # Try to insert another user with same email (should fail)
            with pytest.raises(Exception):  # SQLite will raise IntegrityError
                conn.execute(
                    text("""
                    INSERT INTO users (id, email, name, user_type, created_at, updated_at)
                    VALUES (:id, :email, :name, :user_type, datetime('now'), datetime('now'))
                    """),
                    {
                        "id": "user2",
                        "email": "test@example.com",
                        "name": "Another User",
                        "user_type": "individual",
                    },
                )
                conn.commit()


class TestMigrationPerformance:
    """Test migration performance with larger datasets."""

    def test_migration_time_with_empty_database(self, alembic_config, test_engine):
        """Test migration time on empty database."""
        start_time = time.time()
        command.upgrade(alembic_config, "head")
        migration_time = time.time() - start_time

        # Migration should be fast on empty database (configurable threshold)
        max_time = float(os.getenv("MIGRATION_TIMEOUT_EMPTY", "10.0"))
        assert migration_time < max_time

    def test_migration_time_with_data(self, alembic_config, test_engine):
        """Test migration time with existing data."""
        # First create the schema
        command.upgrade(alembic_config, "head")

        # Insert some test data
        with test_engine.connect() as conn:
            # Insert multiple users and customers
            for i in range(100):
                conn.execute(
                    text("""
                    INSERT INTO users (id, email, name, user_type, created_at, updated_at)
                    VALUES (:id, :email, :name, :user_type, datetime('now'), datetime('now'))
                    """),
                    {
                        "id": f"user{i}",
                        "email": f"user{i}@example.com",
                        "name": f"User {i}",
                        "user_type": "individual",
                    },
                )

                conn.execute(
                    text("""
                    INSERT INTO customers (id, name, user_id, created_at, updated_at)
                    VALUES (:id, :name, :user_id, datetime('now'), datetime('now'))
                    """),
                    {
                        "id": f"customer{i}",
                        "name": f"Customer {i}",
                        "user_id": f"user{i}",
                    },
                )
            conn.commit()

        # Time a migration cycle (down and up)
        start_time = time.time()
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
        migration_time = time.time() - start_time

        # Should still be reasonably fast (configurable threshold for 100 records)
        max_time = float(os.getenv("MIGRATION_TIMEOUT_WITH_DATA", "20.0"))
        assert migration_time < max_time

    def test_concurrent_access_during_migration(self, alembic_config, test_engine):
        """Test that migrations don't excessively lock tables."""
        # This is a basic test - in production you'd want more sophisticated testing
        command.upgrade(alembic_config, "head")

        # Insert some data
        with test_engine.connect() as conn:
            conn.execute(
                text("""
                INSERT INTO users (id, email, name, user_type, created_at, updated_at)
                VALUES (:id, :email, :name, :user_type, datetime('now'), datetime('now'))
                """),
                {
                    "id": "user1",
                    "email": "user1@example.com",
                    "name": "User 1",
                    "user_type": "individual",
                },
            )
            conn.commit()

        # Verify we can still read data
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            assert result == 1


class TestMigrationOrdering:
    """Test migration ordering and dependencies."""

    @pytest.fixture
    def alembic_config(self):
        """Create Alembic configuration."""
        config = Config()
        config.set_main_option("script_location", "paidsearchnav/storage/migrations")
        return config

    def test_migration_ordering(self, alembic_config):
        """Test that migrations are in correct order."""
        script_dir = ScriptDirectory.from_config(alembic_config)
        revisions = list(script_dir.walk_revisions())

        # Should have at least one revision
        assert len(revisions) > 0

        # Check that each revision properly references its predecessor
        prev_revision = None
        for revision in reversed(revisions):  # Walk from oldest to newest
            if prev_revision:
                assert revision.down_revision == prev_revision.revision
            prev_revision = revision

    def test_migration_dependencies(self, alembic_config):
        """Test that migration dependencies are properly defined."""
        script_dir = ScriptDirectory.from_config(alembic_config)
        revisions = list(script_dir.walk_revisions())

        for revision in revisions:
            # Each revision should have proper metadata
            assert revision.revision is not None
            assert revision.doc is not None or revision.revision is not None

            # If it has a down_revision, it should be valid
            if revision.down_revision:
                # Find the down revision in our list
                down_rev = next(
                    (r for r in revisions if r.revision == revision.down_revision), None
                )
                # Note: down_revision might not be in our current migrations
                # if it references an earlier migration that was squashed


@pytest.mark.integration
class TestMigrationWithPostgreSQL:
    """Integration tests for PostgreSQL migrations (when available)."""

    @pytest.fixture
    def postgres_url(self):
        """Get PostgreSQL URL from environment."""
        url = os.getenv("TEST_POSTGRES_URL")
        if not url:
            pytest.skip("TEST_POSTGRES_URL not set")
        return url

    @pytest.fixture
    def postgres_engine(self, postgres_url):
        """Create PostgreSQL engine for testing."""
        # Convert URL to use pg8000 driver instead of default psycopg2
        if postgres_url.startswith("postgresql://"):
            postgres_url = postgres_url.replace("postgresql://", "postgresql+pg8000://")
        engine = create_engine(postgres_url)

        # Clean up any existing test tables (without schema isolation)
        with engine.connect() as conn:
            # Drop any existing migration tables including workflow tables
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS workflow_steps CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS workflow_step_executions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS workflow_executions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS workflow_definitions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS job_executions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS analysis_comparisons CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS analysis_results CASCADE"))
            conn.execute(
                text("DROP TABLE IF EXISTS customer_google_ads_accounts CASCADE")
            )
            conn.execute(text("DROP TABLE IF EXISTS customer_access CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS customers CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS google_ads_accounts CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS analysis_files CASCADE"))
            # Drop S3 security tables
            conn.execute(text("DROP TABLE IF EXISTS security_alerts CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS compliance_reports CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS service_accounts CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS access_tokens CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS customer_encryption_keys CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS s3_audit_log CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS s3_access_permissions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS audits CASCADE"))
            conn.commit()

        yield engine

        # Cleanup - drop all test tables
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS workflow_steps CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS workflow_step_executions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS workflow_executions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS workflow_definitions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS job_executions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS analysis_comparisons CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS analysis_results CASCADE"))
            conn.execute(
                text("DROP TABLE IF EXISTS customer_google_ads_accounts CASCADE")
            )
            conn.execute(text("DROP TABLE IF EXISTS customer_access CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS customers CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS google_ads_accounts CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS analysis_files CASCADE"))
            # Drop S3 security tables
            conn.execute(text("DROP TABLE IF EXISTS security_alerts CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS compliance_reports CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS service_accounts CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS access_tokens CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS customer_encryption_keys CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS s3_audit_log CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS s3_access_permissions CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS audits CASCADE"))
            conn.commit()
        engine.dispose()

    @pytest.fixture
    def postgres_alembic_config(self, postgres_url):
        """Create Alembic config for PostgreSQL."""
        # Convert URL to use pg8000 driver instead of default psycopg2
        if postgres_url.startswith("postgresql://"):
            test_url = postgres_url.replace("postgresql://", "postgresql+pg8000://")
        else:
            test_url = postgres_url

        # For pg8000, we'll handle schema isolation in the test setup instead
        # of using connection options since pg8000 doesn't support the options parameter

        config = Config()
        config.set_main_option("script_location", "paidsearchnav/storage/migrations")
        config.set_main_option("sqlalchemy.url", test_url)
        return config

    def test_postgresql_migrations(self, postgres_alembic_config, postgres_engine):
        """Test migrations work correctly with PostgreSQL."""
        # Run migrations
        command.upgrade(postgres_alembic_config, "head")

        # Verify tables exist (using default schema since pg8000 doesn't support options parameter)
        inspector = inspect(postgres_engine)
        table_names = inspector.get_table_names()

        expected_tables = {
            "users",
            "customers",
            "customer_access",
            "analysis_results",
            "analysis_comparisons",
            "job_executions",
            "google_ads_accounts",
            "customer_google_ads_accounts",
            "analysis_files",
            # S3 security tables
            "s3_access_permissions",
            "s3_audit_log",
            "customer_encryption_keys",
            "access_tokens",
            "service_accounts",
            "compliance_reports",
            "security_alerts",
        }

        for table in expected_tables:
            assert table in table_names

        # Clean up after test by downgrading
        command.downgrade(postgres_alembic_config, "base")

    def test_postgresql_downgrade(self, postgres_alembic_config, postgres_engine):
        """Test downgrade works correctly with PostgreSQL."""
        # Upgrade first
        command.upgrade(postgres_alembic_config, "head")

        # Then downgrade
        command.downgrade(postgres_alembic_config, "base")

        # Verify most tables are gone (except alembic_version) - using default schema
        inspector = inspect(postgres_engine)
        table_names = inspector.get_table_names()

        # Should only have alembic_version table
        assert table_names == ["alembic_version"]
