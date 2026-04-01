"""
消息 ORM 模型
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from backend.database import Base


class MessageRole(str, enum.Enum):
    """消息角色枚举。"""
    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    """
    消息表。
    存储对话中的每一条消息（用户或 AI），
    AI 消息可以关联生成的音频文件。
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 消息角色：user 或 assistant
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    # 消息文字内容
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # AI 消息对应的音频文件 URL（用户消息为 null）
    audio_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 关联关系
    conversation: Mapped["Conversation"] = relationship(  # noqa: F821
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role} conversation_id={self.conversation_id}>"
