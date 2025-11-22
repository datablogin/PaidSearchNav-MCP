"""add_google_ads_accounts_and_relationships

Revision ID: 9dbb9fdced35
Revises: 280f49018197
Create Date: 2025-08-09 23:14:47.695508

"""

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = "9dbb9fdced35"
down_revision = "280f49018197"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Google Ads accounts table and relationships."""
    # Create google_ads_accounts table
    op.create_table(
        "google_ads_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(20), nullable=False, unique=True),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("manager_customer_id", sa.String(20), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Create indexes for google_ads_accounts
    op.create_index(
        "idx_google_ads_customer_id", "google_ads_accounts", ["customer_id"]
    )
    op.create_index(
        "idx_google_ads_manager", "google_ads_accounts", ["manager_customer_id"]
    )

    # Create customer_google_ads_accounts junction table
    op.create_table(
        "customer_google_ads_accounts",
        sa.Column(
            "customer_id",
            sa.String(36),
            sa.ForeignKey("customers.id"),
            primary_key=True,
        ),
        sa.Column(
            "google_ads_account_id",
            sa.String(36),
            sa.ForeignKey("google_ads_accounts.id"),
            primary_key=True,
        ),
        sa.Column("account_role", sa.String(50), nullable=False),
        sa.Column("s3_folder_path", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # Create indexes for junction table
    op.create_index(
        "idx_cga_customer_google_ads",
        "customer_google_ads_accounts",
        ["customer_id", "google_ads_account_id"],
    )
    op.create_index(
        "idx_cga_google_ads_customer",
        "customer_google_ads_accounts",
        ["google_ads_account_id", "customer_id"],
    )

    # Add new columns to customers table
    op.add_column(
        "customers", sa.Column("s3_folder_path", sa.String(500), nullable=True)
    )

    # Add new columns to analysis_results table with batch mode for SQLite compatibility
    with op.batch_alter_table("analysis_results") as batch_op:
        batch_op.add_column(
            sa.Column("google_ads_account_id", sa.String(36), nullable=True)
        )
        batch_op.add_column(sa.Column("s3_input_path", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("s3_output_path", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("audit_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("run_metadata", sa.JSON(), nullable=True))

        # Create foreign key constraints for analysis_results
        batch_op.create_foreign_key(
            "fk_analysis_google_ads_account",
            "google_ads_accounts",
            ["google_ads_account_id"],
            ["id"],
        )

        # Check if audits table exists before creating foreign key
        connection = op.get_bind()
        inspector = sa.inspect(connection)
        if "audits" in inspector.get_table_names():
            batch_op.create_foreign_key(
                "fk_analysis_audit", "audits", ["audit_id"], ["id"]
            )

    # Create indexes for new columns
    op.create_index(
        "idx_google_ads_account", "analysis_results", ["google_ads_account_id"]
    )
    op.create_index("idx_audit_id", "analysis_results", ["audit_id"])

    # Migrate existing data if needed
    # This creates a GoogleAdsAccount for each existing customer with a google_ads_customer_id
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            "SELECT id, google_ads_customer_id, name FROM customers WHERE google_ads_customer_id IS NOT NULL"
        )
    )

    rows = list(result)
    logger.info(f"Migrating {len(rows)} customers to new Google Ads account schema")

    for row in rows:
        customer_id, google_ads_customer_id, customer_name = row

        logger.debug(
            f"Migrating customer {customer_id} with Google Ads ID {google_ads_customer_id}"
        )

        # Insert into google_ads_accounts
        connection.execute(
            sa.text("""
                INSERT INTO google_ads_accounts (id, customer_id, account_name, currency_code, timezone, is_active, created_at, updated_at)
                VALUES (:id, :customer_id, :account_name, 'USD', 'America/New_York', 1, datetime('now'), datetime('now'))
            """),
            {
                "id": customer_id + "-gads",  # Simple ID generation
                "customer_id": google_ads_customer_id,
                "account_name": customer_name + " - Google Ads",
            },
        )

        # Create junction table entry
        connection.execute(
            sa.text("""
                INSERT INTO customer_google_ads_accounts (customer_id, google_ads_account_id, account_role, s3_folder_path, created_at)
                VALUES (:customer_id, :google_ads_account_id, 'owner', :s3_path, datetime('now'))
            """),
            {
                "customer_id": customer_id,
                "google_ads_account_id": customer_id + "-gads",
                "s3_path": f"s3://paidsearchnav-data/{customer_id}/{google_ads_customer_id}",
            },
        )

        # Update customer with S3 path
        connection.execute(
            sa.text("""
                UPDATE customers
                SET s3_folder_path = :s3_path
                WHERE id = :customer_id
            """),
            {
                "customer_id": customer_id,
                "s3_path": f"s3://paidsearchnav-data/{customer_id}",
            },
        )

    # Verify migration data integrity
    if rows:
        migrated_count = connection.execute(
            sa.text("SELECT COUNT(*) FROM google_ads_accounts")
        ).scalar()
        expected_count = len(rows)

        if migrated_count != expected_count:
            raise RuntimeError(
                f"Migration verification failed: expected {expected_count} Google Ads accounts, "
                f"but found {migrated_count}"
            )

        logger.info(
            f"Migration verification passed: {migrated_count} Google Ads accounts created"
        )


def downgrade() -> None:
    """Remove Google Ads accounts table and relationships."""
    # Remove indexes
    op.drop_index("idx_google_ads_account", "analysis_results")
    op.drop_index("idx_audit_id", "analysis_results")

    # Remove columns from analysis_results with batch mode for SQLite compatibility
    with op.batch_alter_table("analysis_results") as batch_op:
        # Remove foreign key constraints
        batch_op.drop_constraint("fk_analysis_google_ads_account", type_="foreignkey")

        # Check if audits table exists before dropping foreign key
        connection = op.get_bind()
        inspector = sa.inspect(connection)
        if "audits" in inspector.get_table_names():
            batch_op.drop_constraint("fk_analysis_audit", type_="foreignkey")

        # Remove columns
        batch_op.drop_column("google_ads_account_id")
        batch_op.drop_column("s3_input_path")
        batch_op.drop_column("s3_output_path")
        batch_op.drop_column("audit_id")
        batch_op.drop_column("run_metadata")

    # Remove column from customers
    op.drop_column("customers", "s3_folder_path")

    # Drop junction table indexes
    op.drop_index("idx_cga_customer_google_ads", "customer_google_ads_accounts")
    op.drop_index("idx_cga_google_ads_customer", "customer_google_ads_accounts")

    # Drop junction table
    op.drop_table("customer_google_ads_accounts")

    # Drop google_ads_accounts indexes
    op.drop_index("idx_google_ads_customer_id", "google_ads_accounts")
    op.drop_index("idx_google_ads_manager", "google_ads_accounts")

    # Drop google_ads_accounts table
    op.drop_table("google_ads_accounts")
