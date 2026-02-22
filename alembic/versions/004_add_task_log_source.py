"""Add source column to task_logs

Revision ID: 004_add_task_log_source
Revises: 003_add_infra_models
Create Date: 2026-02-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_add_task_log_source'
down_revision = '003_add_infra_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'task_logs',
        sa.Column(
            'source',
            sa.String(128),
            nullable=True,
            comment='Agent or service that emitted the log (e.g., orchestrator, developer-agent)',
        ),
    )


def downgrade() -> None:
    op.drop_column('task_logs', 'source')
