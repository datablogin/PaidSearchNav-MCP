"""Add S3 security and access control tables

Revision ID: 5d2a0d79785a
Revises: 9dbb9fdced35
Create Date: 2025-08-10 13:30:14.834040

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import JSON

# revision identifiers, used by Alembic.
revision = "5d2a0d79785a"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create s3_access_permissions table
    op.create_table(
        "s3_access_permissions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("resource_path", sa.String(500), nullable=False),
        sa.Column("permissions", JSON, nullable=False),
        sa.Column("granted_by", sa.String(36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("conditions", JSON, nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for s3_access_permissions
    op.create_index(
        "ix_s3_access_permissions_customer_id", "s3_access_permissions", ["customer_id"]
    )
    op.create_index(
        "ix_s3_access_permissions_user_id", "s3_access_permissions", ["user_id"]
    )
    op.create_index(
        "ix_s3_access_permissions_customer_user",
        "s3_access_permissions",
        ["customer_id", "user_id"],
    )
    op.create_index(
        "ix_s3_access_permissions_expires_at", "s3_access_permissions", ["expires_at"]
    )
    op.create_index(
        "ix_s3_access_permissions_is_active", "s3_access_permissions", ["is_active"]
    )

    # Create s3_audit_log table
    op.create_table(
        "s3_audit_log",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("event_id", sa.String(255), nullable=False, unique=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("customer_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("service_account", sa.String(255), nullable=True),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("resource_path", sa.String(500), nullable=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column(
            "ip_address", sa.String(45), nullable=True
        ),  # Support both IPv4 and IPv6
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(255), nullable=True),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("bytes_transferred", sa.BigInteger(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("result", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", JSON, nullable=True),
        sa.Column("compliance_framework", sa.String(50), nullable=True),
        sa.Column("compliance_requirement", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for s3_audit_log
    op.create_index("ix_s3_audit_log_event_id", "s3_audit_log", ["event_id"])
    op.create_index("ix_s3_audit_log_timestamp", "s3_audit_log", ["timestamp"])
    op.create_index("ix_s3_audit_log_customer_id", "s3_audit_log", ["customer_id"])
    op.create_index("ix_s3_audit_log_user_id", "s3_audit_log", ["user_id"])
    op.create_index("ix_s3_audit_log_event_type", "s3_audit_log", ["event_type"])
    op.create_index("ix_s3_audit_log_operation", "s3_audit_log", ["operation"])
    op.create_index(
        "ix_s3_audit_log_customer_timestamp",
        "s3_audit_log",
        ["customer_id", "timestamp"],
    )

    # Create customer_encryption_keys table
    op.create_table(
        "customer_encryption_keys",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("key_alias", sa.String(255), nullable=False, unique=True),
        sa.Column("kms_key_id", sa.String(255), nullable=True),
        sa.Column("kms_key_arn", sa.String(500), nullable=True),
        sa.Column("key_type", sa.String(50), nullable=False),
        sa.Column("rotation_policy", sa.String(50), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSON, nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for customer_encryption_keys
    op.create_index(
        "ix_customer_encryption_keys_customer_id",
        "customer_encryption_keys",
        ["customer_id"],
    )
    op.create_index(
        "ix_customer_encryption_keys_key_alias",
        "customer_encryption_keys",
        ["key_alias"],
    )
    op.create_index(
        "ix_customer_encryption_keys_enabled", "customer_encryption_keys", ["enabled"]
    )

    # Create access_tokens table for temporary API access
    op.create_table(
        "access_tokens",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("permissions", JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ip_address", sa.String(45), nullable=True
        ),  # Support both IPv4 and IPv6
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "revoked", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for access_tokens
    op.create_index("ix_access_tokens_token_hash", "access_tokens", ["token_hash"])
    op.create_index("ix_access_tokens_customer_id", "access_tokens", ["customer_id"])
    op.create_index("ix_access_tokens_user_id", "access_tokens", ["user_id"])
    op.create_index("ix_access_tokens_expires_at", "access_tokens", ["expires_at"])
    op.create_index("ix_access_tokens_revoked", "access_tokens", ["revoked"])

    # Create service_accounts table
    op.create_table(
        "service_accounts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("service_id", sa.String(255), nullable=False, unique=True),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("api_key_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("permissions", JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSON, nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for service_accounts
    op.create_index(
        "ix_service_accounts_service_id", "service_accounts", ["service_id"]
    )
    op.create_index(
        "ix_service_accounts_customer_id", "service_accounts", ["customer_id"]
    )
    op.create_index(
        "ix_service_accounts_api_key_hash", "service_accounts", ["api_key_hash"]
    )
    op.create_index("ix_service_accounts_enabled", "service_accounts", ["enabled"])

    # Create compliance_reports table
    op.create_table(
        "compliance_reports",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("report_id", sa.String(255), nullable=False, unique=True),
        sa.Column("framework", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("total_events", sa.Integer(), nullable=False),
        sa.Column("violations", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.Integer(), nullable=False),
        sa.Column("requirements_checked", JSON, nullable=False),
        sa.Column("findings", JSON, nullable=True),
        sa.Column("recommendations", JSON, nullable=True),
        sa.Column("report_data", JSON, nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for compliance_reports
    op.create_index(
        "ix_compliance_reports_report_id", "compliance_reports", ["report_id"]
    )
    op.create_index(
        "ix_compliance_reports_framework", "compliance_reports", ["framework"]
    )
    op.create_index(
        "ix_compliance_reports_customer_id", "compliance_reports", ["customer_id"]
    )
    op.create_index(
        "ix_compliance_reports_generated_at", "compliance_reports", ["generated_at"]
    )

    # Create security_alerts table
    op.create_table(
        "security_alerts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("alert_id", sa.String(255), nullable=False, unique=True),
        sa.Column("alert_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("affected_resources", JSON, nullable=True),
        sa.Column("indicators", JSON, nullable=True),
        sa.Column("triggered_by", JSON, nullable=True),
        sa.Column(
            "response_required",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("auto_remediation", sa.Text(), nullable=True),
        sa.Column(
            "resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for security_alerts
    op.create_index("ix_security_alerts_alert_id", "security_alerts", ["alert_id"])
    op.create_index("ix_security_alerts_alert_type", "security_alerts", ["alert_type"])
    op.create_index("ix_security_alerts_severity", "security_alerts", ["severity"])
    op.create_index("ix_security_alerts_timestamp", "security_alerts", ["timestamp"])
    op.create_index(
        "ix_security_alerts_customer_id", "security_alerts", ["customer_id"]
    )
    op.create_index("ix_security_alerts_resolved", "security_alerts", ["resolved"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("security_alerts")
    op.drop_table("compliance_reports")
    op.drop_table("service_accounts")
    op.drop_table("access_tokens")
    op.drop_table("customer_encryption_keys")
    op.drop_table("s3_audit_log")
    op.drop_table("s3_access_permissions")
