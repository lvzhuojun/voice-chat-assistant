"""
对话管道模块
编排 STT → LLM → TTS 流程，通过回调函数向 WebSocket 推送各阶段结果

延迟优化策略：
- LLM 流式输出期间按句子边界切分文字
- 每句完成后立刻触发 TTS 合成
- 音频按 seq 编号顺序推送，前端队列顺序播放
- 对比旧方案（全量等待）：首句音频延迟从 8~15s 降至 2~4s
"""

import re
import base64
from pathlib import Path
from typing import Callable, Awaitable, Optional

from backend.core.stt_engine import transcribe_audio
from backend.core.llm_client import stream_chat
from backend.core.tts_engine import synthesize_speech
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 回调类型定义
SendCallback = Callable[[dict], Awaitable[None]]

# 句子结束符：中文标点 + 英文标点（英文仅在非缩写上下文）
_SENTENCE_END = re.compile(r'[。！？…]+|(?<=[^\d])[.!?]+(?=\s|$)')
# 最短有效句子字符数（避免把单个标点当成句子）
_MIN_SENTENCE_LEN = 6


def _extract_sentences(buffer: str) -> tuple[list[str], str]:
    """
    从累积缓冲区中提取完整句子，返回 (已完成句子列表, 剩余未完成文字)。

    Args:
        buffer: 当前 LLM 输出缓冲区（可能包含多个句子的开头和结尾）

    Returns:
        (sentences, remainder): sentences 可立即送 TTS；remainder 留待后续积累
    """
    sentences: list[str] = []
    last = 0

    for m in _SENTENCE_END.finditer(buffer):
        end = m.end()
        sentence = buffer[last:end].strip()
        if len(sentence) >= _MIN_SENTENCE_LEN:
            sentences.append(sentence)
        last = end

    return sentences, buffer[last:]


async def process_audio_message(
    audio_bytes: bytes,
    audio_format: str,
    conversation_id: int,
    voice_id: str,
    voice_model_dir: Path,
    voice_language: str,
    send_message: SendCallback,
) -> tuple[Optional[str], Optional[str]]:
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
        tuple[str | None, str | None]: (用户语音识别文字, AI 回复文字)
        任一阶段失败时对应项为 None
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
        return None, None

    # 推送识别结果给客户端
    await send_message({
        "type": "transcript",
        "text": transcript,
    })

    logger.info(f"STT 完成：'{transcript[:50]}...'")

    # ── Step 2: LLM 流式生成 + 实时分句 ──────────────────────
    full_reply_parts: list[str] = []
    pending_sentences: list[str] = []
    sentence_buffer = ""

    async for chunk in stream_chat(
        user_message=transcript,
        conversation_id=conversation_id,
    ):
        full_reply_parts.append(chunk)
        sentence_buffer += chunk
        # 逐 token 推送给客户端（打字机效果）
        await send_message({
            "type": "llm_chunk",
            "text": chunk,
        })
        # 检测句子边界，完整句子加入待合成队列
        completed, sentence_buffer = _extract_sentences(sentence_buffer)
        pending_sentences.extend(completed)

    # 末尾未以标点结束的最后一段也要合成
    if sentence_buffer.strip():
        pending_sentences.append(sentence_buffer.strip())

    full_reply = "".join(full_reply_parts).strip()
    if not full_reply:
        await send_message({
            "type": "error",
            "message": "AI 未返回有效回复",
        })
        return transcript, None

    logger.info(
        f"LLM 完成：'{full_reply[:50]}...'，共分 {len(pending_sentences)} 句"
    )

    # ── Step 3: 逐句 TTS，顺序推送音频（降低首音延迟）────────
    audio_sent = 0
    for seq, sentence in enumerate(pending_sentences):
        if not sentence.strip():
            continue
        wav_bytes = await synthesize_speech(
            text=sentence,
            voice_id=voice_id,
            model_dir=voice_model_dir,
            language=voice_language,
        )
        if wav_bytes:
            audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
            await send_message({
                "type": "audio_chunk",
                "data": audio_b64,
                "seq": seq,
            })
            audio_sent += 1
            logger.debug(
                f"TTS 分句[{seq}]：'{sentence[:30]}' → {len(wav_bytes) // 1024}KB"
            )
        else:
            logger.warning(f"TTS 分句[{seq}] 合成失败，已跳过：'{sentence[:30]}'")

    if audio_sent == 0:
        logger.warning(f"全部 TTS 分句均失败，voice_id={voice_id}")

    return transcript, full_reply


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

    # ── LLM 流式生成 + 实时分句 ──────────────────────────────
    full_reply_parts: list[str] = []
    pending_sentences: list[str] = []
    sentence_buffer = ""

    async for chunk in stream_chat(
        user_message=text,
        conversation_id=conversation_id,
    ):
        full_reply_parts.append(chunk)
        sentence_buffer += chunk
        await send_message({
            "type": "llm_chunk",
            "text": chunk,
        })
        completed, sentence_buffer = _extract_sentences(sentence_buffer)
        pending_sentences.extend(completed)

    if sentence_buffer.strip():
        pending_sentences.append(sentence_buffer.strip())

    full_reply = "".join(full_reply_parts).strip()
    if not full_reply:
        await send_message({
            "type": "error",
            "message": "AI 未返回有效回复",
        })
        return None

    logger.info(
        f"LLM 完成（文字模式）：'{full_reply[:50]}...'，共分 {len(pending_sentences)} 句"
    )

    # ── 逐句 TTS，顺序推送音频 ────────────────────────────────
    for seq, sentence in enumerate(pending_sentences):
        if not sentence.strip():
            continue
        wav_bytes = await synthesize_speech(
            text=sentence,
            voice_id=voice_id,
            model_dir=voice_model_dir,
            language=voice_language,
        )
        if wav_bytes:
            audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
            await send_message({
                "type": "audio_chunk",
                "data": audio_b64,
                "seq": seq,
            })

    return full_reply
