"""Initial database schema.

Revision ID: 280f49018197
Revises:
Create Date: 2025-07-04
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "280f49018197"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial database schema with all tables."""
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("user_type", sa.String(20), nullable=False, default="individual"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("idx_users_email", "users", ["email"])

    # Create customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("google_ads_customer_id", sa.String(20), nullable=True, unique=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("settings", sa.JSON(), default={}),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_audit_date", sa.DateTime(), nullable=True),
        sa.Column("next_scheduled_audit", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("idx_customer_user", "customers", ["user_id", "created_at"])
    op.create_index("idx_customer_google_ads", "customers", ["google_ads_customer_id"])

    # Create customer_access table
    op.create_table(
        "customer_access",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False
        ),
        sa.Column("access_level", sa.String(20), nullable=False, default="read"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_access_user_customer",
        "customer_access",
        ["user_id", "customer_id"],
        unique=True,
    )
    op.create_index(
        "idx_access_customer", "customer_access", ["customer_id", "is_active"]
    )

    # Create analysis_results table
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(50), nullable=False),
        sa.Column("analysis_type", sa.String(50), nullable=False),
        sa.Column("analyzer_name", sa.String(100), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="completed"),
        sa.Column("total_recommendations", sa.Integer(), default=0),
        sa.Column("critical_issues", sa.Integer(), default=0),
        sa.Column("potential_cost_savings", sa.Float(), default=0.0),
        sa.Column("potential_conversion_increase", sa.Float(), default=0.0),
        sa.Column("result_data", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_customer_date", "analysis_results", ["customer_id", "created_at"]
    )
    op.create_index(
        "idx_type_date", "analysis_results", ["analysis_type", "created_at"]
    )
    op.create_index(
        "idx_customer_type", "analysis_results", ["customer_id", "analysis_type"]
    )

    # Create analysis_comparisons table
    op.create_table(
        "analysis_comparisons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_id_1", sa.String(36), nullable=False),
        sa.Column("analysis_id_2", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(50), nullable=False),
        sa.Column("comparison_type", sa.String(50), nullable=False),
        sa.Column("comparison_data", sa.JSON(), nullable=False),
        sa.Column("recommendations_added", sa.Integer(), default=0),
        sa.Column("recommendations_resolved", sa.Integer(), default=0),
        sa.Column("cost_savings_change", sa.Float(), default=0.0),
        sa.Column("conversion_change", sa.Float(), default=0.0),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "idx_comparison_customer", "analysis_comparisons", ["customer_id", "created_at"]
    )

    # Create job_executions table
    op.create_table(
        "job_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(100), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(1000), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("idx_job_id_status", "job_executions", ["job_id", "status"])
    op.create_index("idx_job_type_status", "job_executions", ["job_type", "status"])
    op.create_index("idx_started_at", "job_executions", ["started_at"])


def downgrade() -> None:
    """Drop all tables."""
    # Drop job_executions table
    op.drop_index("idx_started_at", "job_executions")
    op.drop_index("idx_job_type_status", "job_executions")
    op.drop_index("idx_job_id_status", "job_executions")
    op.drop_table("job_executions")

    # Drop analysis_comparisons table
    op.drop_index("idx_comparison_customer", "analysis_comparisons")
    op.drop_table("analysis_comparisons")

    # Drop analysis_results table
    op.drop_index("idx_customer_type", "analysis_results")
    op.drop_index("idx_type_date", "analysis_results")
    op.drop_index("idx_customer_date", "analysis_results")
    op.drop_table("analysis_results")

    # Drop customer_access table
    op.drop_index("idx_access_customer", "customer_access")
    op.drop_index("idx_access_user_customer", "customer_access")
    op.drop_table("customer_access")

    # Drop customers table
    op.drop_index("idx_customer_google_ads", "customers")
    op.drop_index("idx_customer_user", "customers")
    op.drop_table("customers")

    # Drop users table
    op.drop_index("idx_users_email", "users")
    op.drop_table("users")
