"""
WebSocket 对话路由
实现全双工语音对话：音频帧/文字消息 → STT→LLM→TTS → 流式推送
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.voice_model import VoiceModel
from backend.core.security import get_token_from_query
from backend.core.pipeline import process_audio_message, process_text_message
from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(tags=["WebSocket"])

# Redis 客户端（懒加载）
_redis = None


async def _get_redis():
    """获取 Redis 客户端。"""
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis.asyncio as redis
        client = redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis = client
    except Exception as e:
        logger.warning(f"WebSocket Redis 不可用：{e}")
    return _redis


async def _get_current_voice(
    user_id: int,
    conversation: Conversation,
    db: AsyncSession,
) -> Optional[VoiceModel]:
    """
    获取当前对话使用的音色。
    优先从 Redis 获取用户当前选择的音色，
    其次从对话关联的音色，最后取用户第一个音色。

    Args:
        user_id: 用户 ID
        conversation: 当前对话
        db: 数据库会话

    Returns:
        VoiceModel 或 None
    """
    # 1. 从 Redis 获取
    redis = await _get_redis()
    voice_id_str = None
    if redis:
        try:
            voice_id_str = await redis.get(f"user:{user_id}:current_voice")
        except Exception:
            pass

    if voice_id_str:
        result = await db.execute(
            select(VoiceModel).where(
                VoiceModel.voice_id == voice_id_str,
                VoiceModel.user_id == user_id,
            )
        )
        voice = result.scalar_one_or_none()
        if voice:
            return voice

    # 2. 从对话关联的音色
    if conversation.voice_model_id:
        result = await db.execute(
            select(VoiceModel).where(VoiceModel.id == conversation.voice_model_id)
        )
        voice = result.scalar_one_or_none()
        if voice:
            return voice

    # 3. 用户第一个音色
    result = await db.execute(
        select(VoiceModel)
        .where(VoiceModel.user_id == user_id, VoiceModel.is_active == True)
        .order_by(VoiceModel.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.websocket("/ws/chat/{conversation_id}")
async def websocket_chat(
    websocket: WebSocket,
    conversation_id: int,
    token: str = Query(..., description="JWT Token"),
) -> None:
    """
    WebSocket 全双工语音对话端点。

    连接地址：ws://host/ws/chat/{conversation_id}?token={jwt}

    客户端 → 服务端：
      - 二进制帧：音频数据（WebM/WAV）
      - 文字帧：{"type":"text","content":"..."}

    服务端 → 客户端：
      - {"type":"transcript","text":"..."}         STT 识别结果
      - {"type":"llm_chunk","text":"..."}          LLM 流式文字
      - {"type":"audio_chunk","data":"base64..."}  TTS 音频
      - {"type":"done","message_id":"..."}         本轮完成
      - {"type":"error","message":"..."}           错误信息

    Args:
        websocket: WebSocket 连接对象
        conversation_id: 对话 ID（URL 路径参数）
        token: JWT Token（Query 参数，WebSocket 无法用 Header）
    """
    # ── 验证 JWT Token ────────────────────────────────────────
    payload = get_token_from_query(token)
    if payload is None:
        await websocket.close(code=4001, reason="无效的认证 Token")
        return

    user_id = int(payload.get("sub", 0))
    if not user_id:
        await websocket.close(code=4001, reason="Token 中缺少用户ID")
        return

    # ── 验证对话权限 ──────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            await websocket.close(code=4004, reason="对话不存在或无权访问")
            return

    # ── 建立 WebSocket 连接 ───────────────────────────────────
    await websocket.accept()
    logger.info(f"WebSocket 连接建立：user={user_id} conv={conversation_id}")

    # 定义发送消息的辅助函数
    async def send_json(data: dict) -> None:
        """安全地向客户端发送 JSON 消息。"""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.warning(f"WebSocket 发送失败：{e}")

    try:
        while True:
            # ── 接收消息 ──────────────────────────────────────
            message = await websocket.receive()

            # 客户端主动断开（切换对话/关闭页面）
            if message.get("type") == "websocket.disconnect":
                logger.info(f"WebSocket 客户端断开：user={user_id} conv={conversation_id}")
                break

            # 判断消息类型
            is_binary = "bytes" in message and message["bytes"] is not None
            is_text = "text" in message and message["text"] is not None

            async with AsyncSessionLocal() as db:
                # 获取当前音色
                voice = await _get_current_voice(user_id, conversation, db)

                if voice is None:
                    await send_json({
                        "type": "error",
                        "message": "没有可用的音色，请先在音色管理页面导入音色",
                    })
                    continue

                # 音色模型目录
                voice_model_dir = Path(voice.gpt_model_path).parent

                # ── 处理音频帧 ────────────────────────────────
                if is_binary:
                    audio_bytes = message["bytes"]
                    if not audio_bytes:
                        continue

                    logger.debug(f"收到音频帧：{len(audio_bytes)} bytes")

                    reply_text = await process_audio_message(
                        audio_bytes=audio_bytes,
                        audio_format="webm",  # 浏览器 MediaRecorder 默认输出 WebM
                        conversation_id=conversation_id,
                        voice_id=voice.voice_id,
                        voice_model_dir=voice_model_dir,
                        voice_language=voice.language,
                        send_message=send_json,
                    )

                    if reply_text:
                        # 存储消息到数据库
                        # 注意：user_content 需要从 transcript 获取，这里简化处理
                        assistant_msg = Message(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=reply_text,
                        )
                        db.add(assistant_msg)
                        await db.commit()
                        await db.refresh(assistant_msg)

                        # 更新对话 updated_at
                        conversation.updated_at = datetime.now(timezone.utc)
                        await db.commit()

                        await send_json({
                            "type": "done",
                            "message_id": str(assistant_msg.id),
                        })

                # ── 处理文字消息 ──────────────────────────────
                elif is_text:
                    text_data = message["text"]
                    try:
                        data = json.loads(text_data)
                    except json.JSONDecodeError:
                        await send_json({
                            "type": "error",
                            "message": "无效的 JSON 格式",
                        })
                        continue

                    msg_type = data.get("type")
                    content = data.get("content", "").strip()

                    if msg_type == "text" and content:
                        logger.debug(f"收到文字消息：{content[:50]}")

                        # 存储用户消息
                        user_msg = Message(
                            conversation_id=conversation_id,
                            role="user",
                            content=content,
                        )
                        db.add(user_msg)
                        await db.commit()

                        reply_text = await process_text_message(
                            text=content,
                            conversation_id=conversation_id,
                            voice_id=voice.voice_id,
                            voice_model_dir=voice_model_dir,
                            voice_language=voice.language,
                            send_message=send_json,
                        )

                        if reply_text:
                            assistant_msg = Message(
                                conversation_id=conversation_id,
                                role="assistant",
                                content=reply_text,
                            )
                            db.add(assistant_msg)
                            await db.commit()
                            await db.refresh(assistant_msg)

                            conversation.updated_at = datetime.now(timezone.utc)
                            await db.commit()

                            await send_json({
                                "type": "done",
                                "message_id": str(assistant_msg.id),
                            })
                    else:
                        logger.debug(f"收到未知消息类型：{msg_type}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开：user={user_id} conv={conversation_id}")
    except Exception as e:
        logger.error(f"WebSocket 错误：{e}", exc_info=True)
        try:
            await send_json({
                "type": "error",
                "message": f"服务器内部错误：{type(e).__name__}",
            })
        except Exception:
            pass
    finally:
        logger.info(f"WebSocket 连接关闭：user={user_id} conv={conversation_id}")
