"""Tests for Google Ads accounts migration."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session


class TestGoogleAdsAccountsMigration:
    """Test the Google Ads accounts migration."""

    @pytest.fixture
    def alembic_config(self, tmp_path):
        """Create Alembic configuration for testing."""
        # Create a test database
        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        # Create config
        config = Config()
        config.set_main_option("script_location", "paidsearchnav/storage/migrations")
        config.set_main_option("sqlalchemy.url", db_url)

        return config, db_url

    @pytest.fixture
    def test_engine(self, alembic_config):
        """Create test engine."""
        _, db_url = alembic_config
        return create_engine(db_url)

    def test_migration_up(self, alembic_config, test_engine):
        """Test applying the migration."""
        config, _ = alembic_config

        # Run migrations up to the parent migration
        command.upgrade(config, "280f49018197")

        # Verify starting state
        inspector = inspect(test_engine)
        tables_before = set(inspector.get_table_names())

        # google_ads_accounts should not exist yet
        assert "google_ads_accounts" not in tables_before
        assert "customer_google_ads_accounts" not in tables_before

        # Check that customers table doesn't have s3_folder_path
        customer_columns = [col["name"] for col in inspector.get_columns("customers")]
        assert "s3_folder_path" not in customer_columns

        # Check that analysis_results doesn't have new columns
        analysis_columns = [
            col["name"] for col in inspector.get_columns("analysis_results")
        ]
        assert "google_ads_account_id" not in analysis_columns
        assert "s3_input_path" not in analysis_columns

        # Run our migration
        command.upgrade(config, "9dbb9fdced35")

        # Verify new tables exist
        inspector = inspect(test_engine)
        tables_after = set(inspector.get_table_names())
        assert "google_ads_accounts" in tables_after
        assert "customer_google_ads_accounts" in tables_after

        # Verify google_ads_accounts columns
        gads_columns = {
            col["name"] for col in inspector.get_columns("google_ads_accounts")
        }
        expected_gads_columns = {
            "id",
            "customer_id",
            "account_name",
            "manager_customer_id",
            "currency_code",
            "timezone",
            "is_active",
            "created_at",
            "updated_at",
        }
        assert expected_gads_columns.issubset(gads_columns)

        # Verify junction table columns
        junction_columns = {
            col["name"] for col in inspector.get_columns("customer_google_ads_accounts")
        }
        expected_junction_columns = {
            "customer_id",
            "google_ads_account_id",
            "account_role",
            "s3_folder_path",
            "created_at",
        }
        assert expected_junction_columns.issubset(junction_columns)

        # Verify customer table updates
        customer_columns = {col["name"] for col in inspector.get_columns("customers")}
        assert "s3_folder_path" in customer_columns

        # Verify analysis_results table updates
        analysis_columns = {
            col["name"] for col in inspector.get_columns("analysis_results")
        }
        assert "google_ads_account_id" in analysis_columns
        assert "s3_input_path" in analysis_columns
        assert "s3_output_path" in analysis_columns
        assert "audit_id" in analysis_columns
        assert "run_metadata" in analysis_columns

        # Verify indexes
        gads_indexes = {
            idx["name"] for idx in inspector.get_indexes("google_ads_accounts")
        }
        assert "idx_google_ads_customer_id" in gads_indexes
        assert "idx_google_ads_manager" in gads_indexes

        junction_indexes = {
            idx["name"] for idx in inspector.get_indexes("customer_google_ads_accounts")
        }
        assert "idx_cga_customer_google_ads" in junction_indexes
        assert "idx_cga_google_ads_customer" in junction_indexes

        analysis_indexes = {
            idx["name"] for idx in inspector.get_indexes("analysis_results")
        }
        assert "idx_google_ads_account" in analysis_indexes
        assert "idx_audit_id" in analysis_indexes

    def test_migration_down(self, alembic_config, test_engine):
        """Test rolling back the migration."""
        config, _ = alembic_config

        # Run migrations up to our migration
        command.upgrade(config, "9dbb9fdced35")

        # Verify tables exist
        inspector = inspect(test_engine)
        assert "google_ads_accounts" in inspector.get_table_names()
        assert "customer_google_ads_accounts" in inspector.get_table_names()

        # Rollback our migration
        command.downgrade(config, "280f49018197")

        # Verify tables are removed
        inspector = inspect(test_engine)
        tables_after_rollback = set(inspector.get_table_names())
        assert "google_ads_accounts" not in tables_after_rollback
        assert "customer_google_ads_accounts" not in tables_after_rollback

        # Verify columns are removed
        customer_columns = {col["name"] for col in inspector.get_columns("customers")}
        assert "s3_folder_path" not in customer_columns

        analysis_columns = {
            col["name"] for col in inspector.get_columns("analysis_results")
        }
        assert "google_ads_account_id" not in analysis_columns
        assert "s3_input_path" not in analysis_columns
        assert "s3_output_path" not in analysis_columns
        assert "audit_id" not in analysis_columns
        assert "run_metadata" not in analysis_columns

    def test_migration_data_preservation(self, alembic_config, test_engine):
        """Test that existing data is preserved and migrated correctly."""
        config, _ = alembic_config

        # Run initial migration
        command.upgrade(config, "280f49018197")

        # Insert test data
        with Session(test_engine) as session:
            # Create users
            session.execute(
                text("""
                INSERT INTO users (id, email, name, user_type, is_active, created_at, updated_at)
                VALUES ('user-1', 'test@example.com', 'Test User', 'individual', 1, datetime('now'), datetime('now'))
            """)
            )

            # Create customers with google_ads_customer_id
            session.execute(
                text("""
                INSERT INTO customers (id, name, user_id, google_ads_customer_id, is_active, created_at, updated_at)
                VALUES
                    ('cust-1', 'Customer 1', 'user-1', '1234567890', 1, datetime('now'), datetime('now')),
                    ('cust-2', 'Customer 2', 'user-1', '0987654321', 1, datetime('now'), datetime('now')),
                    ('cust-3', 'Customer 3', 'user-1', NULL, 1, datetime('now'), datetime('now'))
            """)
            )

            session.commit()

        # Run our migration
        command.upgrade(config, "9dbb9fdced35")

        # Verify data migration
        with Session(test_engine) as session:
            # Check google_ads_accounts table
            result = session.execute(
                text("SELECT COUNT(*) FROM google_ads_accounts")
            ).scalar()
            assert result == 2  # Only customers with google_ads_customer_id

            # Check specific account
            account = session.execute(
                text("""
                SELECT customer_id, account_name, currency_code, timezone
                FROM google_ads_accounts
                WHERE customer_id = '1234567890'
            """)
            ).fetchone()
            assert account is not None
            assert account[0] == "1234567890"
            assert "Customer 1" in account[1]
            assert account[2] == "USD"
            assert account[3] == "America/New_York"

            # Check junction table
            junction_count = session.execute(
                text("SELECT COUNT(*) FROM customer_google_ads_accounts")
            ).scalar()
            assert junction_count == 2

            # Check customer S3 paths
            customer = session.execute(
                text("""
                SELECT s3_folder_path
                FROM customers
                WHERE id = 'cust-1'
            """)
            ).fetchone()
            assert customer[0] is not None
            assert "s3://paidsearchnav-data/cust-1" in customer[0]

            # Verify customer without google_ads_customer_id has no S3 path
            customer3 = session.execute(
                text("""
                SELECT s3_folder_path
                FROM customers
                WHERE id = 'cust-3'
            """)
            ).fetchone()
            assert customer3[0] is None

    def test_migration_idempotency(self, alembic_config, test_engine):
        """Test that migration can be safely run multiple times."""
        config, _ = alembic_config

        # Run migration
        command.upgrade(config, "9dbb9fdced35")

        # Get state after first run
        inspector = inspect(test_engine)
        tables_first_run = set(inspector.get_table_names())

        # Try to run again (should not fail)
        command.upgrade(config, "9dbb9fdced35")

        # Verify state is unchanged
        tables_second_run = set(inspector.get_table_names())
        assert tables_first_run == tables_second_run

    def test_foreign_key_constraints(self, alembic_config, test_engine):
        """Test that foreign key constraints are properly created."""
        config, _ = alembic_config

        # Run migration
        command.upgrade(config, "9dbb9fdced35")

        # Get foreign keys
        inspector = inspect(test_engine)

        # Check junction table foreign keys
        junction_fks = inspector.get_foreign_keys("customer_google_ads_accounts")
        fk_tables = {fk["referred_table"] for fk in junction_fks}
        assert "customers" in fk_tables
        assert "google_ads_accounts" in fk_tables

        # Check analysis_results foreign keys
        analysis_fks = inspector.get_foreign_keys("analysis_results")
        fk_tables = {
            fk["referred_table"] for fk in analysis_fks if fk["referred_table"]
        }
        assert "google_ads_accounts" in fk_tables
        # Only check for audits FK if audits table exists
        if "audits" in inspector.get_table_names():
            assert "audits" in fk_tables
