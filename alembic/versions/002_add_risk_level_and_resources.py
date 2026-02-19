"""Add risk_level to approval_requests and platform_resources table

Revision ID: 002_add_risk_level_and_resources
Revises: 001_initial_schema
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_risk_level_and_resources'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add risk_level column to approval_requests
    op.add_column(
        'approval_requests',
        sa.Column(
            'risk_level',
            sa.String(32),
            nullable=False,
            server_default='NONE',
            comment='NONE | LOW | MEDIUM | HIGH | CRITICAL',
        ),
    )

    # Create platform_resources table
    op.create_table(
        'platform_resources',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('uuid_generate_v4()'),
        ),
        sa.Column(
            'task_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('tasks.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'platform',
            sa.String(32),
            nullable=False,
            comment='databricks or fabric',
        ),
        sa.Column(
            'resource_type',
            sa.String(64),
            nullable=False,
            comment='pipeline, job, table, shortcut',
        ),
        sa.Column(
            'platform_resource_id',
            sa.String(256),
            nullable=False,
            comment='ID assigned by the platform',
        ),
        sa.Column(
            'definition',
            postgresql.JSONB,
            nullable=True,
            comment='Full resource definition/configuration',
        ),
        sa.Column(
            'status',
            sa.String(32),
            nullable=False,
            server_default='CREATED',
            comment='CREATED | QUEUED | RUNNING | COMPLETED | FAILED',
        ),
        sa.Column(
            'metadata',
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )

    op.create_index('ix_platform_resources_task_id', 'platform_resources', ['task_id'])
    op.create_index('ix_platform_resources_platform', 'platform_resources', ['platform'])
    op.create_index('ix_platform_resources_type', 'platform_resources', ['resource_type'])


def downgrade() -> None:
    op.drop_index('ix_platform_resources_type', 'platform_resources')
    op.drop_index('ix_platform_resources_platform', 'platform_resources')
    op.drop_index('ix_platform_resources_task_id', 'platform_resources')
    op.drop_table('platform_resources')
    op.drop_column('approval_requests', 'risk_level')
