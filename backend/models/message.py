"""
消息 ORM 模型
Message ORM model.
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from backend.database import Base


class MessageRole(str, enum.Enum):
    """
    消息角色枚举。
    Enumeration of message roles.
    """
    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    """
    消息表。
    存储对话中的每一条消息（用户或 AI），
    AI 消息可以关联生成的音频文件。
    Messages table.
    Stores every message in a conversation (user or AI).
    AI messages may be associated with a generated audio file.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 消息角色：user 或 assistant / Message role: user or assistant
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    # 消息文字内容 / Text content of the message
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # AI 消息对应的音频文件 URL（用户消息为 null）
    # Audio file URL for AI messages (NULL for user messages)
    audio_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 关联关系 / Relationships
    conversation: Mapped["Conversation"] = relationship(  # noqa: F821
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role} conversation_id={self.conversation_id}>"
