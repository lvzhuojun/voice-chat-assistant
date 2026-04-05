"""
Pydantic Schema 定义
用于 FastAPI 请求/响应的数据验证和序列化
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field, field_validator


# ═══════════════════════════════════════════════════════════════
# 认证相关 Schema
# ═══════════════════════════════════════════════════════════════

class UserRegisterRequest(BaseModel):
    """用户注册请求体。"""
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, description="密码（至少8位，须包含字母和数字）")
    username: str = Field(..., min_length=1, max_length=100, description="用户名")

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含至少一个字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含至少一个数字")
        return v


class UserLoginRequest(BaseModel):
    """用户登录请求体。"""
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户信息响应。"""
    id: int
    email: str
    username: str
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT Token 响应。"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ═══════════════════════════════════════════════════════════════
# 音色模型相关 Schema
# ═══════════════════════════════════════════════════════════════

class VoiceModelResponse(BaseModel):
    """音色模型信息响应。"""
    id: int
    voice_id: str
    voice_name: str
    language: str
    gpt_model_path: str
    sovits_model_path: str
    reference_wav_path: str
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class VoiceModelListItem(BaseModel):
    """音色模型列表项（精简版）。"""
    id: int
    voice_id: str
    voice_name: str
    language: str
    created_at: datetime
    is_active: bool
    metadata_json: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class VoiceSelectResponse(BaseModel):
    """设置当前音色的响应。"""
    message: str
    voice_id: str


# ═══════════════════════════════════════════════════════════════
# 对话相关 Schema
# ═══════════════════════════════════════════════════════════════

class ConversationCreateRequest(BaseModel):
    """创建对话请求体。"""
    title: str = Field(default="新对话", max_length=255, description="对话标题")
    voice_model_id: Optional[int] = Field(default=None, description="使用的音色 ID")


class ConversationTitleUpdateRequest(BaseModel):
    """更新对话标题请求体。"""
    title: str = Field(..., min_length=1, max_length=255, description="新标题")


class ConversationResponse(BaseModel):
    """对话信息响应。"""
    id: int
    title: str
    voice_model_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationWithCount(ConversationResponse):
    """带消息数量的对话信息响应。"""
    message_count: int = 0


class MessageResponse(BaseModel):
    """消息信息响应。"""
    id: int
    conversation_id: int
    role: str
    content: str
    audio_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# 通用响应 Schema
# ═══════════════════════════════════════════════════════════════

class SimpleMessageResponse(BaseModel):
    """简单消息响应（用于删除等操作）。"""
    message: str


class HealthResponse(BaseModel):
    """健康检查响应。"""
    status: str
    gpu: dict[str, Any]
    whisper_loaded: bool
    tts_models_loaded: int
    voice_count: int
