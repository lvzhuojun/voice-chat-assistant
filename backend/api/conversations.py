"""
对话历史管理 API 路由
Conversation history management API routes.
提供对话的 CRUD 和消息查询接口
Provides CRUD operations for conversations and message retrieval endpoints.
"""

from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.database import get_db
from backend.models.user import User
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.schemas.schemas import (
    ConversationCreateRequest,
    ConversationTitleUpdateRequest,
    ConversationResponse,
    ConversationWithCount,
    MessageResponse,
    SimpleMessageResponse,
)
from backend.core.security import get_current_user
from backend.core.llm_client import clear_conversation_context
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["对话管理"])


@router.get("", response_model=list[ConversationWithCount])
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ConversationWithCount]:
    """
    获取当前用户的对话列表（按更新时间倒序）。
    Retrieve the current user's conversation list (ordered by update time, descending).
    同时返回每个对话的消息数量。
    Also returns the message count for each conversation.

    Args:
        current_user: 当前登录用户 / Currently authenticated user
        db: 数据库会话 / Database session

    Returns:
        list[ConversationWithCount]: 对话列表（含消息数） / Conversation list with message counts
    """
    # 单次查询：LEFT JOIN 消息数子查询，避免 N+1 问题
    # Single query: LEFT JOIN with a message-count subquery to avoid the N+1 problem
    msg_count_subq = (
        select(
            Message.conversation_id,
            func.count(Message.id).label("cnt"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    rows = await db.execute(
        select(Conversation, func.coalesce(msg_count_subq.c.cnt, 0).label("message_count"))
        .outerjoin(msg_count_subq, Conversation.id == msg_count_subq.c.conversation_id)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )

    response_list = [
        ConversationWithCount(
            id=conv.id,
            title=conv.title,
            voice_model_id=conv.voice_model_id,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=message_count,
        )
        for conv, message_count in rows
    ]

    return response_list


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationResponse:
    """
    创建新对话。
    Create a new conversation.

    Args:
        request: 创建请求（title、voice_model_id 可选） / Creation request (title and voice_model_id are optional)
        current_user: 当前登录用户 / Currently authenticated user
        db: 数据库会话 / Database session

    Returns:
        ConversationResponse: 创建的对话信息 / Information about the newly created conversation
    """
    conversation = Conversation(
        user_id=current_user.id,
        title=request.title or "新对话",
        voice_model_id=request.voice_model_id,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    logger.info(
        f"用户 {current_user.email} 创建对话：{conversation.title} (id={conversation.id})"
    )
    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[MessageResponse]:
    """
    获取指定对话的消息列表（按时间升序）。
    Retrieve the message list for a specific conversation (ordered by time, ascending).

    Args:
        conversation_id: 对话 ID / Conversation ID
        current_user: 当前登录用户 / Currently authenticated user
        db: 数据库会话 / Database session

    Returns:
        list[MessageResponse]: 消息列表 / List of messages
    """
    # 验证对话归属 / Verify that the conversation belongs to the current user
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在或无权访问",
        )

    # 获取消息列表（按时间升序） / Fetch messages ordered by creation time ascending
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = msg_result.scalars().all()
    return [MessageResponse.model_validate(m) for m in messages]


@router.delete("/{conversation_id}", response_model=SimpleMessageResponse)
async def delete_conversation(
    conversation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimpleMessageResponse:
    """
    删除对话及其所有消息。
    Delete a conversation and all of its messages.
    同时清除 Redis 中的 LLM 上下文缓存。
    Also clears the LLM context cache stored in Redis.

    Args:
        conversation_id: 对话 ID / Conversation ID
        current_user: 当前登录用户 / Currently authenticated user
        db: 数据库会话 / Database session

    Returns:
        SimpleMessageResponse: 操作结果 / Operation result
    """
    # 验证对话归属 / Verify that the conversation belongs to the current user
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在或无权访问",
        )

    # 清除 LLM 上下文缓存（Redis） / Clear the LLM context cache from Redis
    await clear_conversation_context(conversation_id)

    # 删除对话（级联删除消息，通过 ORM cascade 配置）
    # Delete the conversation (messages are cascade-deleted via ORM cascade configuration)
    await db.delete(conversation)
    await db.commit()

    logger.info(f"用户 {current_user.email} 删除对话 id={conversation_id}")
    return SimpleMessageResponse(message="对话已删除")


@router.patch("/{conversation_id}/title", response_model=ConversationResponse)
async def update_conversation_title(
    conversation_id: int,
    body: ConversationTitleUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationResponse:
    """
    更新对话标题。
    Update the title of a conversation.

    Args:
        conversation_id: 对话 ID / Conversation ID
        body: 包含新标题的请求体 / Request body containing the new title
        current_user: 当前登录用户 / Currently authenticated user
        db: 数据库会话 / Database session

    Returns:
        ConversationResponse: 更新后的对话信息 / Updated conversation information
    """
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在或无权访问",
        )

    conversation.title = body.title
    conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(conversation)

    return ConversationResponse.model_validate(conversation)
