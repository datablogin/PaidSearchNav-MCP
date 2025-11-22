"""Add analysis_files table for S3 file tracking

Revision ID: a1b2c3d4e5f6
Revises: 9dbb9fdced35
Create Date: 2025-01-11

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9dbb9fdced35"
branch_labels = None
depends_on = None


def upgrade():
    """Add analysis_files table and related indexes."""
    # Create analysis_files table
    op.create_table(
        "analysis_files",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "analysis_id",
            sa.String(36),
            sa.ForeignKey("analysis_results.id"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_category", sa.String(20), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("file_metadata", sa.JSON(), nullable=True, default={}),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )

    # Create indexes
    op.create_index(
        "idx_analysis_files_analysis",
        "analysis_files",
        ["analysis_id", "file_category"],
    )
    op.create_index("idx_analysis_files_category", "analysis_files", ["file_category"])
    op.create_index("idx_analysis_files_created", "analysis_files", ["created_at"])


def downgrade():
    """Remove analysis_files table and indexes."""
    # Drop indexes first
    op.drop_index("idx_analysis_files_created", table_name="analysis_files")
    op.drop_index("idx_analysis_files_category", table_name="analysis_files")
    op.drop_index("idx_analysis_files_analysis", table_name="analysis_files")

    # Drop table
    op.drop_table("analysis_files")
