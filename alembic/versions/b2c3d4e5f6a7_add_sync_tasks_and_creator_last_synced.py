"""add sync_tasks table and last_synced_at to creators

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sync_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('total_creators', sa.Integer(), nullable=False),
        sa.Column('completed_creators', sa.Integer(), nullable=False),
        sa.Column('current_creator_name', sa.String(length=255), nullable=True),
        sa.Column('new_videos', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.String(length=1024), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('heartbeat_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('creators', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_synced_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('creators', schema=None) as batch_op:
        batch_op.drop_column('last_synced_at')
    op.drop_table('sync_tasks')
