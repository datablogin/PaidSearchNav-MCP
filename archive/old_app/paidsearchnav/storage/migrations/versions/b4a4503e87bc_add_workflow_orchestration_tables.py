"""Add workflow orchestration tables

Revision ID: b4a4503e87bc
Revises: d2e3f4g5h6i7
Create Date: 2025-08-17 19:35:28.623049

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b4a4503e87bc"
down_revision = "d2e3f4g5h6i7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create workflow_definitions table
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Create indexes for workflow_definitions
    op.create_index("idx_workflow_def_name", "workflow_definitions", ["name"])
    op.create_index(
        "idx_workflow_def_name_version", "workflow_definitions", ["name", "version"]
    )
    op.create_index("idx_workflow_def_enabled", "workflow_definitions", ["enabled"])

    # Create workflow_executions table
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workflow_definition_id",
            sa.String(36),
            sa.ForeignKey("workflow_definitions.id"),
            nullable=False,
        ),
        sa.Column(
            "customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("current_step", sa.String(255), nullable=True),
        sa.Column("context", sa.JSON(), default={}),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Create indexes for workflow_executions
    op.create_index(
        "idx_workflow_exec_workflow_definition_id",
        "workflow_executions",
        ["workflow_definition_id"],
    )
    op.create_index(
        "idx_workflow_exec_customer_id", "workflow_executions", ["customer_id"]
    )
    op.create_index(
        "idx_workflow_exec_status", "workflow_executions", ["status", "created_at"]
    )
    op.create_index(
        "idx_workflow_exec_customer", "workflow_executions", ["customer_id", "status"]
    )
    op.create_index(
        "idx_workflow_exec_definition",
        "workflow_executions",
        ["workflow_definition_id", "status"],
    )
    op.create_index("idx_workflow_exec_started", "workflow_executions", ["started_at"])

    # Create workflow_step_executions table
    op.create_table(
        "workflow_step_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "execution_id",
            sa.String(36),
            sa.ForeignKey("workflow_executions.id"),
            nullable=False,
        ),
        sa.Column("step_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # Create indexes for workflow_step_executions
    op.create_index(
        "idx_workflow_step_exec_execution_id",
        "workflow_step_executions",
        ["execution_id"],
    )
    op.create_index(
        "idx_workflow_step_exec_execution",
        "workflow_step_executions",
        ["execution_id", "created_at"],
    )
    op.create_index(
        "idx_workflow_step_exec_status", "workflow_step_executions", ["status"]
    )
    op.create_index(
        "idx_workflow_step_exec_name", "workflow_step_executions", ["step_name"]
    )


def downgrade() -> None:
    # Drop indexes for workflow_step_executions
    op.drop_index("idx_workflow_step_exec_name", "workflow_step_executions")
    op.drop_index("idx_workflow_step_exec_status", "workflow_step_executions")
    op.drop_index("idx_workflow_step_exec_execution", "workflow_step_executions")
    op.drop_index("idx_workflow_step_exec_execution_id", "workflow_step_executions")

    # Drop workflow_step_executions table
    op.drop_table("workflow_step_executions")

    # Drop indexes for workflow_executions
    op.drop_index("idx_workflow_exec_started", "workflow_executions")
    op.drop_index("idx_workflow_exec_definition", "workflow_executions")
    op.drop_index("idx_workflow_exec_customer", "workflow_executions")
    op.drop_index("idx_workflow_exec_status", "workflow_executions")
    op.drop_index("idx_workflow_exec_customer_id", "workflow_executions")
    op.drop_index("idx_workflow_exec_workflow_definition_id", "workflow_executions")

    # Drop workflow_executions table
    op.drop_table("workflow_executions")

    # Drop indexes for workflow_definitions
    op.drop_index("idx_workflow_def_enabled", "workflow_definitions")
    op.drop_index("idx_workflow_def_name_version", "workflow_definitions")
    op.drop_index("idx_workflow_def_name", "workflow_definitions")

    # Drop workflow_definitions table
    op.drop_table("workflow_definitions")
