"""add_api_workflow_tables

Revision ID: c1d2e3f4g5h6
Revises: b7c8d9e10f11
Create Date: 2025-01-13 10:00:00.000000

"""

import logging
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

logger = logging.getLogger(__name__)


def _get_json_type():
    """Get appropriate JSON type based on database backend."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return JSONB()
    else:
        return sa.JSON()


# revision identifiers, used by Alembic.
revision = "c1d2e3f4g5h6"
down_revision = "b7c8d9e10f11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add API workflow and token storage tables."""

    # Create api_workflows table for tracking workflow executions
    op.create_table(
        "api_workflows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("workflow_id", sa.String(36), nullable=False, unique=True),
        sa.Column("execution_id", sa.String(36), nullable=False, unique=True),
        sa.Column("customer_id", sa.String(20), nullable=False),
        sa.Column("workflow_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("priority", sa.String(20), default="normal"),
        sa.Column("dry_run", sa.Boolean(), default=True),
        sa.Column("auto_rollback", sa.Boolean(), default=True),
        sa.Column("total_operations", sa.Integer(), default=0),
        sa.Column("completed_operations", sa.Integer(), default=0),
        sa.Column("failed_operations", sa.Integer(), default=0),
        sa.Column("progress_percentage", sa.Float(), default=0.0),
        sa.Column("metadata", _get_json_type(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("rollback_completed", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("estimated_completion", sa.DateTime(), nullable=True),
    )

    # Create workflow_steps table for tracking individual steps
    op.create_table(
        "workflow_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("step_id", sa.String(36), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("operation_type", sa.String(50), nullable=False),
        sa.Column("operation_data", _get_json_type(), nullable=False),
        sa.Column("depends_on", sa.JSON(), nullable=True),  # Array of step IDs
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("max_retries", sa.Integer(), default=3),
        sa.Column("timeout_seconds", sa.Integer(), default=300),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("rollback_data", _get_json_type(), nullable=True),
        sa.Column(
            "results", _get_json_type(), nullable=True
        ),  # Array of operation results
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["api_workflows.workflow_id"],
            name="fk_workflow_steps_workflow_id",
            ondelete="CASCADE",
        ),
    )

    # Create google_ads_tokens table for OAuth token storage
    op.create_table(
        "google_ads_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("customer_id", sa.String(20), nullable=False, unique=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "token_uri", sa.String(255), default="https://oauth2.googleapis.com/token"
        ),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("client_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=True),  # Array of scopes
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("granted_at", sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column("granted_by_user", sa.String(255), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=True),  # Array of permissions
        sa.Column("consent_metadata", _get_json_type(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column("updated_at", sa.DateTime(), default=datetime.utcnow, nullable=False),
    )

    # Create oauth_consent_flows table for tracking OAuth flows
    op.create_table(
        "oauth_consent_flows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("flow_id", sa.String(36), nullable=False, unique=True),
        sa.Column("customer_id", sa.String(20), nullable=False),
        sa.Column("state", sa.String(255), nullable=False, unique=True),
        sa.Column("requested_permissions", sa.JSON(), nullable=False),
        sa.Column("authorization_url", sa.Text(), nullable=True),
        sa.Column("callback_received", sa.Boolean(), default=False),
        sa.Column("user_info", _get_json_type(), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("created_at", sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # Create recommendations table for tracking recommendations
    op.create_table(
        "api_recommendations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("recommendation_id", sa.String(36), nullable=False, unique=True),
        sa.Column("customer_id", sa.String(20), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(20), default="medium"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("campaign_ids", sa.JSON(), nullable=True),  # Array of campaign IDs
        sa.Column("ad_group_ids", sa.JSON(), nullable=True),  # Array of ad group IDs
        sa.Column(
            "data", _get_json_type(), nullable=False
        ),  # Recommendation-specific data
        sa.Column("metadata", _get_json_type(), nullable=True),
        sa.Column("auto_approve", sa.Boolean(), default=False),
        sa.Column("dry_run", sa.Boolean(), default=True),
        sa.Column("rollback_window_hours", sa.Integer(), default=24),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("execution_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("operations_count", sa.Integer(), default=0),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("analysis_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # Create recommendation_batches table for batch operations
    op.create_table(
        "recommendation_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("batch_id", sa.String(36), nullable=False, unique=True),
        sa.Column("customer_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("dry_run", sa.Boolean(), default=True),
        sa.Column("auto_rollback", sa.Boolean(), default=True),
        sa.Column("priority", sa.String(20), default="normal"),
        sa.Column("total_recommendations", sa.Integer(), default=0),
        sa.Column("completed_recommendations", sa.Integer(), default=0),
        sa.Column("failed_recommendations", sa.Integer(), default=0),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("created_at", sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # Create junction table for recommendations in batches
    op.create_table(
        "batch_recommendations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("recommendation_id", sa.String(36), nullable=False),
        sa.Column("execution_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["recommendation_batches.batch_id"],
            name="fk_batch_recommendations_batch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["api_recommendations.recommendation_id"],
            name="fk_batch_recommendations_recommendation_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "batch_id", "recommendation_id", name="uq_batch_recommendation"
        ),
    )

    # Create indexes for better query performance

    # api_workflows indexes
    op.create_index("idx_api_workflows_customer_id", "api_workflows", ["customer_id"])
    op.create_index("idx_api_workflows_status", "api_workflows", ["status"])
    op.create_index(
        "idx_api_workflows_workflow_type", "api_workflows", ["workflow_type"]
    )
    op.create_index("idx_api_workflows_created_at", "api_workflows", ["created_at"])
    op.create_index("idx_api_workflows_started_at", "api_workflows", ["started_at"])
    op.create_index("idx_api_workflows_priority", "api_workflows", ["priority"])

    # workflow_steps indexes
    op.create_index("idx_workflow_steps_workflow_id", "workflow_steps", ["workflow_id"])
    op.create_index("idx_workflow_steps_status", "workflow_steps", ["status"])
    op.create_index(
        "idx_workflow_steps_operation_type", "workflow_steps", ["operation_type"]
    )

    # google_ads_tokens indexes
    op.create_index(
        "idx_google_ads_tokens_customer_id", "google_ads_tokens", ["customer_id"]
    )
    op.create_index(
        "idx_google_ads_tokens_expires_at", "google_ads_tokens", ["expires_at"]
    )
    op.create_index(
        "idx_google_ads_tokens_is_active", "google_ads_tokens", ["is_active"]
    )

    # oauth_consent_flows indexes
    op.create_index(
        "idx_oauth_flows_customer_id", "oauth_consent_flows", ["customer_id"]
    )
    op.create_index("idx_oauth_flows_state", "oauth_consent_flows", ["state"])
    op.create_index("idx_oauth_flows_expires_at", "oauth_consent_flows", ["expires_at"])
    op.create_index("idx_oauth_flows_status", "oauth_consent_flows", ["status"])

    # api_recommendations indexes
    op.create_index(
        "idx_api_recommendations_customer_id", "api_recommendations", ["customer_id"]
    )
    op.create_index("idx_api_recommendations_type", "api_recommendations", ["type"])
    op.create_index(
        "idx_api_recommendations_priority", "api_recommendations", ["priority"]
    )
    op.create_index("idx_api_recommendations_status", "api_recommendations", ["status"])
    op.create_index(
        "idx_api_recommendations_workflow_id", "api_recommendations", ["workflow_id"]
    )
    op.create_index(
        "idx_api_recommendations_created_at", "api_recommendations", ["created_at"]
    )

    # recommendation_batches indexes
    op.create_index(
        "idx_recommendation_batches_customer_id",
        "recommendation_batches",
        ["customer_id"],
    )
    op.create_index(
        "idx_recommendation_batches_status", "recommendation_batches", ["status"]
    )
    op.create_index(
        "idx_recommendation_batches_created_at",
        "recommendation_batches",
        ["created_at"],
    )

    # batch_recommendations indexes
    op.create_index(
        "idx_batch_recommendations_batch_id", "batch_recommendations", ["batch_id"]
    )
    op.create_index(
        "idx_batch_recommendations_recommendation_id",
        "batch_recommendations",
        ["recommendation_id"],
    )
    op.create_index(
        "idx_batch_recommendations_execution_order",
        "batch_recommendations",
        ["execution_order"],
    )

    logger.info("Created API workflow and token storage tables")


def downgrade() -> None:
    """Remove API workflow and token storage tables."""

    # Drop indexes first
    op.drop_index("idx_batch_recommendations_execution_order", "batch_recommendations")
    op.drop_index(
        "idx_batch_recommendations_recommendation_id", "batch_recommendations"
    )
    op.drop_index("idx_batch_recommendations_batch_id", "batch_recommendations")

    op.drop_index("idx_recommendation_batches_created_at", "recommendation_batches")
    op.drop_index("idx_recommendation_batches_status", "recommendation_batches")
    op.drop_index("idx_recommendation_batches_customer_id", "recommendation_batches")

    op.drop_index("idx_api_recommendations_created_at", "api_recommendations")
    op.drop_index("idx_api_recommendations_workflow_id", "api_recommendations")
    op.drop_index("idx_api_recommendations_status", "api_recommendations")
    op.drop_index("idx_api_recommendations_priority", "api_recommendations")
    op.drop_index("idx_api_recommendations_type", "api_recommendations")
    op.drop_index("idx_api_recommendations_customer_id", "api_recommendations")

    op.drop_index("idx_oauth_flows_status", "oauth_consent_flows")
    op.drop_index("idx_oauth_flows_expires_at", "oauth_consent_flows")
    op.drop_index("idx_oauth_flows_state", "oauth_consent_flows")
    op.drop_index("idx_oauth_flows_customer_id", "oauth_consent_flows")

    op.drop_index("idx_google_ads_tokens_is_active", "google_ads_tokens")
    op.drop_index("idx_google_ads_tokens_expires_at", "google_ads_tokens")
    op.drop_index("idx_google_ads_tokens_customer_id", "google_ads_tokens")

    op.drop_index("idx_workflow_steps_operation_type", "workflow_steps")
    op.drop_index("idx_workflow_steps_status", "workflow_steps")
    op.drop_index("idx_workflow_steps_workflow_id", "workflow_steps")

    op.drop_index("idx_api_workflows_priority", "api_workflows")
    op.drop_index("idx_api_workflows_started_at", "api_workflows")
    op.drop_index("idx_api_workflows_created_at", "api_workflows")
    op.drop_index("idx_api_workflows_workflow_type", "api_workflows")
    op.drop_index("idx_api_workflows_status", "api_workflows")
    op.drop_index("idx_api_workflows_customer_id", "api_workflows")

    # Drop tables in reverse dependency order
    op.drop_table("batch_recommendations")
    op.drop_table("recommendation_batches")
    op.drop_table("api_recommendations")
    op.drop_table("oauth_consent_flows")
    op.drop_table("google_ads_tokens")
    op.drop_table("workflow_steps")
    op.drop_table("api_workflows")

    logger.info("Dropped API workflow and token storage tables")
