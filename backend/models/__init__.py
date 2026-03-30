"""
ORM 模型包
导入所有模型，确保 Alembic 可以发现它们
"""

from backend.models.user import User
from backend.models.voice_model import VoiceModel
from backend.models.conversation import Conversation
from backend.models.message import Message, MessageRole

__all__ = ["User", "VoiceModel", "Conversation", "Message", "MessageRole"]
