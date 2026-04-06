"""为 voice_models 表添加 tts_engine 列
Add the tts_engine column to the voice_models table.

支持双引擎模式：gptsovits（默认，保持向后兼容）和 cosyvoice2。
Enables dual-engine mode: gptsovits (default, backward-compatible) and cosyvoice2.

Revision ID: 002
Revises: 001
Create Date: 2026-04-05 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    添加 tts_engine 列，默认值 gptsovits（存量数据全部归为 GPT-SoVITS 引擎）。
    Add the tts_engine column with a default of 'gptsovits'
    so that all existing rows are classified under the GPT-SoVITS engine.
    """
    op.add_column(
        "voice_models",
        sa.Column(
            "tts_engine",
            sa.String(length=20),
            nullable=False,
            server_default="gptsovits",
        ),
    )


def downgrade() -> None:
    """
    回滚：删除 tts_engine 列。
    Rollback: drop the tts_engine column.
    """
    op.drop_column("voice_models", "tts_engine")
