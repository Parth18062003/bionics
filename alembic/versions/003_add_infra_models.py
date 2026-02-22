"""Add TaskLog, CostRecord, PlatformConnection models

Revision ID: 003_add_infra_models
Revises: 002_add_risk_level_and_resources
Create Date: 2026-02-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_add_infra_models'
down_revision = '002_add_risk_level_and_resources'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create task_logs table
    op.create_table(
        'task_logs',
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
            'level',
            sa.String(16),
            nullable=False,
            comment='DEBUG | INFO | WARNING | ERROR',
        ),
        sa.Column(
            'message',
            sa.Text,
            nullable=False,
        ),
        sa.Column(
            'correlation_id',
            sa.String(64),
            nullable=True,
            comment='Links to HTTP request correlation ID',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )

    op.create_index('ix_task_logs_task_id', 'task_logs', ['task_id'])
    op.create_index('ix_task_logs_created_at', 'task_logs', ['created_at'])

    # Create cost_records table
    op.create_table(
        'cost_records',
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
            'agent_type',
            sa.String(32),
            nullable=False,
            comment='orchestrator | developer | validation | optimizer',
        ),
        sa.Column(
            'tokens_in',
            sa.Integer,
            nullable=False,
        ),
        sa.Column(
            'tokens_out',
            sa.Integer,
            nullable=False,
        ),
        sa.Column(
            'cost_usd',
            sa.Numeric(10, 6),
            nullable=False,
            comment='Cost in USD with 6 decimal precision',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )

    op.create_index('ix_cost_records_task_id', 'cost_records', ['task_id'])
    op.create_index('ix_cost_records_created_at', 'cost_records', ['created_at'])

    # Create platform_connections table
    op.create_table(
        'platform_connections',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('uuid_generate_v4()'),
        ),
        sa.Column(
            'platform',
            sa.String(32),
            nullable=False,
            comment='databricks | fabric',
        ),
        sa.Column(
            'name',
            sa.String(128),
            nullable=False,
            comment='Human-readable connection name',
        ),
        sa.Column(
            'config',
            postgresql.JSONB,
            nullable=False,
            comment='Encrypted connection configuration',
        ),
        sa.Column(
            'is_active',
            sa.Boolean,
            nullable=False,
            server_default=sa.text('true'),
            comment='Whether this connection is currently active',
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

    op.create_index('ix_platform_connections_platform', 'platform_connections', ['platform'])
    op.create_index('ix_platform_connections_is_active', 'platform_connections', ['is_active'])


def downgrade() -> None:
    # Drop platform_connections table
    op.drop_index('ix_platform_connections_is_active', 'platform_connections')
    op.drop_index('ix_platform_connections_platform', 'platform_connections')
    op.drop_table('platform_connections')

    # Drop cost_records table
    op.drop_index('ix_cost_records_created_at', 'cost_records')
    op.drop_index('ix_cost_records_task_id', 'cost_records')
    op.drop_table('cost_records')

    # Drop task_logs table
    op.drop_index('ix_task_logs_created_at', 'task_logs')
    op.drop_index('ix_task_logs_task_id', 'task_logs')
    op.drop_table('task_logs')
