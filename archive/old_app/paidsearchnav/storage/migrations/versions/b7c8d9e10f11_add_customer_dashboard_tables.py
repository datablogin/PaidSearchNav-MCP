"""Add customer dashboard tables

Revision ID: b7c8d9e10f11
Revises: 5d2a0d79785a
Create Date: 2025-08-11 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7c8d9e10f11"
down_revision = "5d2a0d79785a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tables for customer dashboard and management."""

    # Create user_sessions table for session management
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_token", sa.String(255), unique=True, nullable=False),
        sa.Column("refresh_token", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),  # Support IPv6
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("last_activity", sa.DateTime(), nullable=True),
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

    # Create indexes for user_sessions
    op.create_index("idx_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("idx_user_sessions_token", "user_sessions", ["session_token"])
    op.create_index("idx_user_sessions_expires", "user_sessions", ["expires_at"])

    # Create api_keys table for API access
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "rate_limit", sa.Integer(), nullable=True
        ),  # Custom rate limit per key
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_ip", sa.String(45), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
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

    # Create indexes for api_keys
    op.create_index("idx_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("idx_api_keys_hash", "api_keys", ["key_hash"])
    op.create_index("idx_api_keys_enabled", "api_keys", ["enabled", "expires_at"])

    # Create dashboard_configs table for user preferences
    op.create_table(
        "dashboard_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "config_type", sa.String(50), nullable=False
        ),  # 'layout', 'filters', 'preferences', 'widgets'
        sa.Column("config_name", sa.String(255), nullable=False),
        sa.Column("config_data", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
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

    # Create indexes for dashboard_configs
    op.create_index(
        "idx_dashboard_configs_user", "dashboard_configs", ["user_id", "config_type"]
    )
    op.create_index(
        "idx_dashboard_configs_default",
        "dashboard_configs",
        ["user_id", "config_type", "is_default"],
    )

    # Create workflow_status table for real-time workflow tracking
    op.create_table(
        "workflow_status",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "customer_id",
            sa.String(36),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_type", sa.String(50), nullable=False
        ),  # 'analysis', 'export', 'script_execution'
        sa.Column(
            "workflow_id", sa.String(100), nullable=False
        ),  # External workflow ID
        sa.Column(
            "status", sa.String(20), nullable=False
        ),  # 'pending', 'running', 'completed', 'failed'
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("current_step", sa.String(255), nullable=True),
        sa.Column("total_steps", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
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

    # Create indexes for workflow_status
    op.create_index(
        "idx_workflow_status_customer", "workflow_status", ["customer_id", "status"]
    )
    op.create_index(
        "idx_workflow_status_type", "workflow_status", ["workflow_type", "status"]
    )
    op.create_index(
        "idx_workflow_status_workflow_id", "workflow_status", ["workflow_id"]
    )

    # Create customer_metrics table for business intelligence
    op.create_table(
        "customer_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "customer_id",
            sa.String(36),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column(
            "metric_type", sa.String(50), nullable=False
        ),  # 'usage', 'performance', 'cost'
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("metric_unit", sa.String(20), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )

    # Create indexes for customer_metrics
    op.create_index(
        "idx_customer_metrics_customer_date",
        "customer_metrics",
        ["customer_id", "metric_date"],
    )
    op.create_index(
        "idx_customer_metrics_type_date",
        "customer_metrics",
        ["metric_type", "metric_date"],
    )
    op.create_index(
        "idx_customer_metrics_unique",
        "customer_metrics",
        ["customer_id", "metric_date", "metric_type", "metric_name"],
        unique=True,
    )

    # Create user_notifications table for dashboard notifications
    op.create_table(
        "user_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "notification_type", sa.String(50), nullable=False
        ),  # 'info', 'warning', 'error', 'success'
        sa.Column(
            "category", sa.String(50), nullable=False
        ),  # 'audit', 'system', 'workflow', 'report'
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )

    # Create indexes for user_notifications
    op.create_index(
        "idx_user_notifications_user", "user_notifications", ["user_id", "read_at"]
    )
    op.create_index(
        "idx_user_notifications_expires", "user_notifications", ["expires_at"]
    )

    # Create audit_logs table for comprehensive audit logging
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "customer_id",
            sa.String(36),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("request_method", sa.String(10), nullable=True),
        sa.Column("request_path", sa.String(500), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )

    # Create indexes for audit_logs
    op.create_index("idx_audit_logs_user", "audit_logs", ["user_id", "created_at"])
    op.create_index(
        "idx_audit_logs_customer", "audit_logs", ["customer_id", "created_at"]
    )
    op.create_index("idx_audit_logs_action", "audit_logs", ["action", "created_at"])
    op.create_index(
        "idx_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"]
    )

    # Add new columns to existing users table for enhanced auth
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column(
        "users", sa.Column("password_updated_at", sa.DateTime(), nullable=True)
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("last_login_ip", sa.String(45), nullable=True))
    op.add_column(
        "users", sa.Column("failed_login_attempts", sa.Integer(), server_default="0")
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))
    op.add_column(
        "users", sa.Column("two_factor_enabled", sa.Boolean(), server_default="false")
    )
    op.add_column(
        "users", sa.Column("two_factor_secret", sa.String(255), nullable=True)
    )
    op.add_column("users", sa.Column("preferences", sa.JSON(), nullable=True))

    # Add role column to users table for RBAC
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), nullable=False, server_default="customer"),
    )
    op.create_index("idx_users_role", "users", ["role"])

    # Add composite indexes for common query patterns
    op.create_index(
        "idx_user_sessions_user_expires",
        "user_sessions",
        ["user_id", "expires_at"],
    )
    op.create_index(
        "idx_api_keys_user_enabled",
        "api_keys",
        ["user_id", "enabled"],
    )
    op.create_index(
        "idx_workflow_status_customer_created",
        "workflow_status",
        ["customer_id", "created_at"],
    )
    op.create_index(
        "idx_customer_metrics_customer_type_date",
        "customer_metrics",
        ["customer_id", "metric_type", "metric_date"],
    )
    op.create_index(
        "idx_audit_logs_user_action_created",
        "audit_logs",
        ["user_id", "action", "created_at"],
    )


def downgrade() -> None:
    """Drop customer dashboard tables."""

    # Drop composite indexes
    op.drop_index("idx_audit_logs_user_action_created", table_name="audit_logs")
    op.drop_index(
        "idx_customer_metrics_customer_type_date", table_name="customer_metrics"
    )
    op.drop_index("idx_workflow_status_customer_created", table_name="workflow_status")
    op.drop_index("idx_api_keys_user_enabled", table_name="api_keys")
    op.drop_index("idx_user_sessions_user_expires", table_name="user_sessions")

    # Remove new columns from users table
    op.drop_index("idx_users_role", table_name="users")
    op.drop_column("users", "role")
    op.drop_column("users", "preferences")
    op.drop_column("users", "two_factor_secret")
    op.drop_column("users", "two_factor_enabled")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
    op.drop_column("users", "last_login_ip")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "password_updated_at")
    op.drop_column("users", "password_hash")

    # Drop indexes and tables in reverse order
    op.drop_index("idx_audit_logs_resource", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action", table_name="audit_logs")
    op.drop_index("idx_audit_logs_customer", table_name="audit_logs")
    op.drop_index("idx_audit_logs_user", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("idx_user_notifications_expires", table_name="user_notifications")
    op.drop_index("idx_user_notifications_user", table_name="user_notifications")
    op.drop_table("user_notifications")

    op.drop_index("idx_customer_metrics_unique", table_name="customer_metrics")
    op.drop_index("idx_customer_metrics_type_date", table_name="customer_metrics")
    op.drop_index("idx_customer_metrics_customer_date", table_name="customer_metrics")
    op.drop_table("customer_metrics")

    op.drop_index("idx_workflow_status_workflow_id", table_name="workflow_status")
    op.drop_index("idx_workflow_status_type", table_name="workflow_status")
    op.drop_index("idx_workflow_status_customer", table_name="workflow_status")
    op.drop_table("workflow_status")

    op.drop_index("idx_dashboard_configs_default", table_name="dashboard_configs")
    op.drop_index("idx_dashboard_configs_user", table_name="dashboard_configs")
    op.drop_table("dashboard_configs")

    op.drop_index("idx_api_keys_enabled", table_name="api_keys")
    op.drop_index("idx_api_keys_hash", table_name="api_keys")
    op.drop_index("idx_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index("idx_user_sessions_expires", table_name="user_sessions")
    op.drop_index("idx_user_sessions_token", table_name="user_sessions")
    op.drop_index("idx_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
