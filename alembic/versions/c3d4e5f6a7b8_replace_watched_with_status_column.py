"""replace watched bool with status int column

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-12 14:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('video_statuses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.Integer(), nullable=False, server_default='0'))

    op.execute("UPDATE video_statuses SET status = 1 WHERE watched = 1")

    with op.batch_alter_table('video_statuses', schema=None) as batch_op:
        batch_op.drop_column('watched')


def downgrade() -> None:
    with op.batch_alter_table('video_statuses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('watched', sa.Boolean(), nullable=False, server_default='0'))

    op.execute("UPDATE video_statuses SET watched = 1 WHERE status = 1")

    with op.batch_alter_table('video_statuses', schema=None) as batch_op:
        batch_op.drop_column('status')
