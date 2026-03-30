"""
对话管道模块
编排 STT → LLM → TTS 流程，通过回调函数向 WebSocket 推送各阶段结果
"""

import base64
import io
from pathlib import Path
from typing import Callable, Awaitable, Optional

from backend.core.stt_engine import transcribe_audio
from backend.core.llm_client import stream_chat
from backend.core.tts_engine import synthesize_speech
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 回调类型定义
SendCallback = Callable[[dict], Awaitable[None]]


async def process_audio_message(
    audio_bytes: bytes,
    audio_format: str,
    conversation_id: int,
    voice_id: str,
    voice_model_dir: Path,
    voice_language: str,
    send_message: SendCallback,
) -> Optional[str]:
    """
    处理音频输入消息，执行完整的 STT→LLM→TTS 管道。

    各阶段会通过 send_message 回调实时向客户端推送进度：
    - STT 完成 → transcript
    - LLM 流式 → llm_chunk（逐 token）
    - TTS 完成 → audio_chunk（base64）

    Args:
        audio_bytes: 音频字节流（WebM/WAV）
        audio_format: 音频格式（webm/wav）
        conversation_id: 对话 ID
        voice_id: 当前使用的音色 UUID
        voice_model_dir: 音色模型目录
        voice_language: 音色语言（用于 TTS）
        send_message: WebSocket 发送回调

    Returns:
        str: AI 回复完整文字（用于写入数据库），失败返回 None
    """
    # ── Step 1: STT 语音识别 ──────────────────────────────────
    logger.info(f"管道开始：STT → conv={conversation_id}")

    transcript = await transcribe_audio(
        audio_bytes,
        audio_format=audio_format,
    )

    if not transcript:
        await send_message({
            "type": "error",
            "message": "语音识别失败，请检查麦克风或重试",
        })
        return None

    # 推送识别结果给客户端
    await send_message({
        "type": "transcript",
        "text": transcript,
    })

    logger.info(f"STT 完成：'{transcript[:50]}...'")

    # ── Step 2 & 3: LLM 流式生成 + 收集全文 ──────────────────
    full_reply_parts = []

    async for chunk in stream_chat(
        user_message=transcript,
        conversation_id=conversation_id,
    ):
        full_reply_parts.append(chunk)
        # 逐 token 推送给客户端
        await send_message({
            "type": "llm_chunk",
            "text": chunk,
        })

    full_reply = "".join(full_reply_parts).strip()
    if not full_reply:
        await send_message({
            "type": "error",
            "message": "AI 未返回有效回复",
        })
        return transcript  # 仍然返回识别文字

    logger.info(f"LLM 完成：'{full_reply[:50]}...'")

    # ── Step 3: TTS 语音合成 ──────────────────────────────────
    wav_bytes = await synthesize_speech(
        text=full_reply,
        voice_id=voice_id,
        model_dir=voice_model_dir,
        language=voice_language,
    )

    if wav_bytes:
        # 将 WAV bytes 编码为 base64 推送
        audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
        await send_message({
            "type": "audio_chunk",
            "data": audio_b64,
        })
        logger.info(f"TTS 完成，音频大小：{len(wav_bytes) // 1024}KB")
    else:
        logger.warning(f"TTS 合成失败，voice_id={voice_id}，但文字回复已发送")
        # TTS 失败不阻断流程，文字回复已推送

    return full_reply


async def process_text_message(
    text: str,
    conversation_id: int,
    voice_id: str,
    voice_model_dir: Path,
    voice_language: str,
    send_message: SendCallback,
) -> Optional[str]:
    """
    处理文字输入消息，执行 LLM→TTS 管道（跳过 STT）。

    Args:
        text: 用户文字输入
        conversation_id: 对话 ID
        voice_id: 当前使用的音色 UUID
        voice_model_dir: 音色模型目录
        voice_language: 音色语言
        send_message: WebSocket 发送回调

    Returns:
        str: AI 回复完整文字，失败返回 None
    """
    logger.info(f"文字消息管道：text='{text[:50]}...' conv={conversation_id}")

    # ── LLM 流式生成 ──────────────────────────────────────────
    full_reply_parts = []

    async for chunk in stream_chat(
        user_message=text,
        conversation_id=conversation_id,
    ):
        full_reply_parts.append(chunk)
        await send_message({
            "type": "llm_chunk",
            "text": chunk,
        })

    full_reply = "".join(full_reply_parts).strip()
    if not full_reply:
        await send_message({
            "type": "error",
            "message": "AI 未返回有效回复",
        })
        return None

    logger.info(f"LLM 完成（文字模式）：'{full_reply[:50]}...'")

    # ── TTS 语音合成 ──────────────────────────────────────────
    wav_bytes = await synthesize_speech(
        text=full_reply,
        voice_id=voice_id,
        model_dir=voice_model_dir,
        language=voice_language,
    )

    if wav_bytes:
        audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
        await send_message({
            "type": "audio_chunk",
            "data": audio_b64,
        })

    return full_reply
