"""Add version tracking to artifacts

Revision ID: 005_add_artifact_version
Revises: 004_add_task_log_source
Create Date: 2026-02-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_artifact_version'
down_revision = '004_add_task_log_source'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add version column with default 1 for existing rows
    op.add_column(
        'artifacts',
        sa.Column(
            'version',
            sa.Integer,
            nullable=False,
            server_default=sa.text('1'),
            comment='Version number, increments on each save',
        ),
    )

    # Add parent_id column for version lineage (self-referencing FK)
    op.add_column(
        'artifacts',
        sa.Column(
            'parent_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('artifacts.id', ondelete='SET NULL'),
            nullable=True,
            comment='Parent artifact for version lineage',
        ),
    )

    # Add edit_message column for describing version changes
    op.add_column(
        'artifacts',
        sa.Column(
            'edit_message',
            sa.Text,
            nullable=True,
            comment='Optional message describing this version\'s changes',
        ),
    )

    # Add composite index for efficient version queries by task
    op.create_index('ix_artifacts_task_version', 'artifacts', ['task_id', 'version'])


def downgrade() -> None:
    op.drop_index('ix_artifacts_task_version', 'artifacts')
    op.drop_column('artifacts', 'edit_message')
    op.drop_column('artifacts', 'parent_id')
    op.drop_column('artifacts', 'version')
