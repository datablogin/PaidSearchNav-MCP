"""Add composite index for workflow performance optimization

Revision ID: 507d83655135
Revises: b4a4503e87bc
Create Date: 2025-08-17 20:49:57.362144

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "507d83655135"
down_revision = "b4a4503e87bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add composite index for finding active workflows per customer
    op.create_index(
        "idx_workflow_exec_customer_definition_status",
        "workflow_executions",
        ["customer_id", "workflow_definition_id", "status"],
    )


def downgrade() -> None:
    # Remove composite index
    op.drop_index("idx_workflow_exec_customer_definition_status", "workflow_executions")
