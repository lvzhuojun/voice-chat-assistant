"""
音色模型 ORM 模型
存储导入的音色信息，支持 GPT-SoVITS（gptsovits）和 CosyVoice 2（cosyvoice2）两种推理引擎
"""

from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database import Base


class VoiceModel(Base):
    """
    音色模型表。
    每条记录对应一个从 voice-cloning-service 导入的音色，
    包含模型文件路径和元数据。
    """

    __tablename__ = "voice_models"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    # 用户外键
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 音色基本信息（来自 metadata.json）
    voice_name: Mapped[str] = mapped_column(String(255), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)  # UUID
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="zh")

    # TTS 推理引擎（gptsovits | cosyvoice2）
    # CosyVoice 2 使用共享基础模型+参考音频，无需专属模型文件
    tts_engine: Mapped[str] = mapped_column(
        String(20), nullable=False, default="gptsovits", server_default="gptsovits"
    )

    # 模型文件路径（相对于项目根目录）
    # CosyVoice 2 音色的 gpt_model_path / sovits_model_path 为空字符串
    gpt_model_path: Mapped[str] = mapped_column(String(512), nullable=False, default="", server_default="")
    sovits_model_path: Mapped[str] = mapped_column(String(512), nullable=False, default="", server_default="")
    reference_wav_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # 原始 metadata.json 内容（JSON 字段，保留完整训练信息）
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 关联关系
    user: Mapped["User"] = relationship("User", back_populates="voice_models")  # noqa: F821
    conversations: Mapped[list["Conversation"]] = relationship(  # noqa: F821
        "Conversation",
        back_populates="voice_model",
    )

    def __repr__(self) -> str:
        return f"<VoiceModel id={self.id} name={self.voice_name} voice_id={self.voice_id}>"
