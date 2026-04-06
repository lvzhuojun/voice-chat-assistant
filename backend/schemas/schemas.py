"""
Pydantic Schema 定义
用于 FastAPI 请求/响应的数据验证和序列化
Pydantic schema definitions for FastAPI request/response data validation and serialization.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field, field_validator


# ═══════════════════════════════════════════════════════════════
# 认证相关 Schema
# Authentication-related schemas
# ═══════════════════════════════════════════════════════════════

class UserRegisterRequest(BaseModel):
    """
    用户注册请求体。
    Request body for user registration.
    """
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
    """
    用户登录请求体。
    Request body for user login.
    """
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """
    用户信息响应。
    Response schema for user information.
    """
    id: int
    email: str
    username: str
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """
    JWT Token 响应。
    Response schema for JWT access token.
    """
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ═══════════════════════════════════════════════════════════════
# 音色模型相关 Schema
# Voice model-related schemas
# ═══════════════════════════════════════════════════════════════

class VoiceModelResponse(BaseModel):
    """
    音色模型信息响应。
    Response schema for a full voice model record.
    """
    id: int
    voice_id: str
    voice_name: str
    language: str
    tts_engine: str = "gptsovits"
    gpt_model_path: str
    sovits_model_path: str
    reference_wav_path: str
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class VoiceModelListItem(BaseModel):
    """
    音色模型列表项（精简版）。
    Abbreviated voice model item used in list responses.
    """
    id: int
    voice_id: str
    voice_name: str
    language: str
    tts_engine: str = "gptsovits"
    created_at: datetime
    is_active: bool
    metadata_json: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class VoiceSelectResponse(BaseModel):
    """
    设置当前音色的响应。
    Response schema for the set-active-voice operation.
    """
    message: str
    voice_id: str


# ═══════════════════════════════════════════════════════════════
# 对话相关 Schema
# Conversation-related schemas
# ═══════════════════════════════════════════════════════════════

class ConversationCreateRequest(BaseModel):
    """
    创建对话请求体。
    Request body for creating a new conversation.
    """
    title: str = Field(default="新对话", max_length=255, description="对话标题")
    voice_model_id: Optional[int] = Field(default=None, description="使用的音色 ID")


class ConversationTitleUpdateRequest(BaseModel):
    """
    更新对话标题请求体。
    Request body for updating a conversation title.
    """
    title: str = Field(..., min_length=1, max_length=255, description="新标题")


class ConversationResponse(BaseModel):
    """
    对话信息响应。
    Response schema for a conversation record.
    """
    id: int
    title: str
    voice_model_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationWithCount(ConversationResponse):
    """
    带消息数量的对话信息响应。
    Conversation response extended with a message count field.
    """
    message_count: int = 0


class MessageResponse(BaseModel):
    """
    消息信息响应。
    Response schema for a single chat message.
    """
    id: int
    conversation_id: int
    role: str
    content: str
    audio_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# 通用响应 Schema
# Generic response schemas
# ═══════════════════════════════════════════════════════════════

class SimpleMessageResponse(BaseModel):
    """
    简单消息响应（用于删除等操作）。
    Generic message response used for operations such as deletion.
    """
    message: str


class HealthResponse(BaseModel):
    """
    健康检查响应。
    Response schema for the health-check endpoint.
    """
    status: str
    gpu: dict[str, Any]
    whisper_loaded: bool
    tts_models_loaded: int
    voice_count: int
