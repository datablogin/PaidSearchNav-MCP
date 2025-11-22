"""Fix workflow step dependencies with proper foreign keys

Revision ID: d2e3f4g5h6i7
Revises: c1d2e3f4g5h6
Create Date: 2025-01-13 14:00:00.000000

"""

import logging
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = "d2e3f4g5h6i7"
down_revision = "c1d2e3f4g5h6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Fix workflow step dependencies with proper foreign key relationships."""

    # Create workflow_step_dependencies table for proper many-to-many relationships
    op.create_table(
        "workflow_step_dependencies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("step_id", sa.String(36), nullable=False),
        sa.Column("depends_on_step_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.ForeignKeyConstraint(
            ["step_id"],
            ["workflow_steps.step_id"],
            name="fk_step_deps_step_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_step_id"],
            ["workflow_steps.step_id"],
            name="fk_step_deps_depends_on",
            ondelete="CASCADE",
        ),
        # Prevent duplicate dependencies
        sa.UniqueConstraint("step_id", "depends_on_step_id", name="uq_step_dependency"),
    )

    # Add index for performance
    op.create_index(
        "ix_workflow_step_dependencies_step_id",
        "workflow_step_dependencies",
        ["step_id"],
    )
    op.create_index(
        "ix_workflow_step_dependencies_depends_on",
        "workflow_step_dependencies",
        ["depends_on_step_id"],
    )

    # Migrate existing data from JSON depends_on field to the new table
    # First, we need to get all existing workflow steps with dependencies
    connection = op.get_bind()

    # Query existing steps with dependencies
    result = connection.execute(
        sa.text(
            "SELECT step_id, depends_on FROM workflow_steps WHERE depends_on IS NOT NULL"
        )
    )

    for row in result:
        step_id = row.step_id
        depends_on = row.depends_on

        if isinstance(depends_on, list):
            # Insert dependency records
            for dependency_step_id in depends_on:
                try:
                    connection.execute(
                        sa.text(
                            "INSERT INTO workflow_step_dependencies (id, step_id, depends_on_step_id, created_at) "
                            "VALUES (:id, :step_id, :depends_on_step_id, :created_at)"
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "step_id": step_id,
                            "depends_on_step_id": dependency_step_id,
                            "created_at": datetime.utcnow(),
                        },
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to migrate dependency {step_id} -> {dependency_step_id}: {e}"
                    )

    # Remove the old JSON depends_on column
    op.drop_column("workflow_steps", "depends_on")

    logger.info("Successfully migrated workflow step dependencies to normalized schema")


def downgrade() -> None:
    """Revert workflow step dependencies back to JSON format."""

    # Add back the depends_on JSON column
    op.add_column("workflow_steps", sa.Column("depends_on", sa.JSON(), nullable=True))

    # Migrate data back to JSON format
    connection = op.get_bind()

    # Get all unique step_ids first
    step_result = connection.execute(
        sa.text("SELECT DISTINCT step_id FROM workflow_step_dependencies")
    )

    for step_row in step_result:
        step_id = step_row.step_id

        # Get all dependencies for this step_id using individual queries
        # This works for both PostgreSQL and SQLite
        dep_result = connection.execute(
            sa.text(
                "SELECT depends_on_step_id FROM workflow_step_dependencies "
                "WHERE step_id = :step_id"
            ),
            {"step_id": step_id},
        )

        # Collect dependencies into a list
        dependencies = [row.depends_on_step_id for row in dep_result]

        # Update workflow_steps with JSON dependencies
        connection.execute(
            sa.text(
                "UPDATE workflow_steps SET depends_on = :depends_on WHERE step_id = :step_id"
            ),
            {
                "step_id": step_id,
                "depends_on": dependencies,
            },
        )

    # Drop the normalized dependency table
    op.drop_index("ix_workflow_step_dependencies_depends_on")
    op.drop_index("ix_workflow_step_dependencies_step_id")
    op.drop_table("workflow_step_dependencies")

    logger.info("Successfully reverted workflow step dependencies to JSON format")
