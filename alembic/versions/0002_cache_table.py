"""添加 fetcher 缓存表。"""
from alembic import op
import sqlalchemy as sa

revision = "0002_cache_table"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cache",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("cache")
