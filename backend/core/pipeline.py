"""
对话管道模块
Conversation pipeline module.
编排 STT → LLM → TTS 流程，通过回调函数向 WebSocket 推送各阶段结果
Orchestrates the STT → LLM → TTS pipeline, pushing stage results to WebSocket via callbacks.

延迟优化策略：
Latency optimization strategy:
- LLM 流式输出期间按句子边界切分文字
  Split text at sentence boundaries during LLM streaming output
- 检测到句子边界时立即创建 TTS 异步任务（asyncio.create_task），
  与 LLM 继续输出并行进行
  Immediately create a TTS async task (asyncio.create_task) upon detecting a sentence boundary,
  running in parallel with continued LLM output
- LLM 完成后按 seq 顺序等待各 TTS 任务，保证音频发送顺序
  After LLM finishes, await TTS tasks in seq order to guarantee audio delivery order
- 对比旧方案（全量等待再逐句 TTS）：首句音频延迟从 8~15s 降至 2~4s
  Compared to the old approach (wait for full LLM output then TTS sentence by sentence):
  first-sentence audio latency reduced from 8~15s to 2~4s
"""

import asyncio
import re
import base64
from pathlib import Path
from typing import Callable, Awaitable, Optional

from backend.core.stt_engine import transcribe_audio
from backend.core.llm_client import stream_chat, LLM_ERROR_MARKER
from backend.core.tts_engine import synthesize_speech
from backend.core.tts_engine_cosyvoice import synthesize_speech_cosyvoice
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 回调类型定义 / Callback type definition
SendCallback = Callable[[dict], Awaitable[None]]

# 句子结束符：中文标点 + 英文标点（英文仅在非缩写上下文）
# Sentence-end punctuation: Chinese marks + English marks (English only in non-abbreviation context)
_SENTENCE_END = re.compile(r'[。！？…]+|(?<=[^\d])[.!?]+(?=\s|$)')
# 最短有效句子字符数（避免把单个标点当成句子；3 可容纳 "好。" "OK." 等短回答）
# Minimum valid sentence character count (avoids treating a lone punctuation mark as a sentence;
# 3 accommodates short answers such as "好。" or "OK.")
_MIN_SENTENCE_LEN = 3


def _extract_sentences(buffer: str) -> tuple[list[str], str]:
    """
    从累积缓冲区中提取完整句子，返回 (已完成句子列表, 剩余未完成文字)。
    Extract complete sentences from the accumulated buffer, returning (completed sentences, remaining text).

    Args:
        buffer: 当前 LLM 输出缓冲区（可能包含多个句子的开头和结尾）
                / Current LLM output buffer (may contain partial starts and ends of multiple sentences)

    Returns:
        (sentences, remainder): sentences 可立即送 TTS；remainder 留待后续积累
        / (sentences, remainder): sentences are ready for TTS; remainder is held for further accumulation
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
    tts_engine: str = "gptsovits",
) -> tuple[Optional[str], Optional[str]]:
    """
    处理音频输入消息，执行完整的 STT→LLM→TTS 管道。
    Process an audio input message, executing the full STT→LLM→TTS pipeline.

    各阶段会通过 send_message 回调实时向客户端推送进度：
    Each stage pushes progress to the client in real time via the send_message callback:
    - STT 完成 → transcript / STT complete → transcript
    - LLM 流式 → llm_chunk（逐 token）/ LLM streaming → llm_chunk (token by token)
    - TTS 完成 → audio_chunk（base64，按 seq 顺序）/ TTS complete → audio_chunk (base64, in seq order)

    Args:
        audio_bytes: 音频字节流（WebM/WAV）/ Audio byte stream (WebM/WAV)
        audio_format: 音频格式（webm/wav）/ Audio format (webm/wav)
        conversation_id: 对话 ID / Conversation ID
        voice_id: 当前使用的音色 UUID / UUID of the currently selected voice
        voice_model_dir: 音色模型目录 / Voice model directory
        voice_language: 音色语言（用于 TTS）/ Voice language (used for TTS)
        send_message: WebSocket 发送回调 / WebSocket send callback

    Returns:
        tuple[str | None, str | None]: (用户语音识别文字, AI 回复文字)
        / (transcribed user speech text, AI reply text)
        任一阶段失败时对应项为 None / The corresponding item is None when any stage fails
    """
    # ── Step 1: STT 语音识别 / Speech recognition ──────────────────────────────
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

    await send_message({
        "type": "transcript",
        "text": transcript,
    })

    logger.info(f"STT 完成：'{transcript[:50]}...'")

    # ── Step 2+3: LLM 流式生成 + 并行 TTS / LLM streaming + parallel TTS ───────
    # 每检测到句子边界立即创建 TTS 任务，与 LLM 继续输出并发执行，
    # 最后按顺序等待各任务并推送音频，保证前端播放顺序。
    # A TTS task is created immediately upon each detected sentence boundary, running
    # concurrently with continued LLM output. Tasks are awaited in order and audio is
    # pushed sequentially to guarantee correct playback order on the frontend.
    full_reply, audio_sent = await _llm_tts_pipeline(
        user_message=transcript,
        conversation_id=conversation_id,
        voice_id=voice_id,
        voice_model_dir=voice_model_dir,
        voice_language=voice_language,
        send_message=send_message,
        tts_engine=tts_engine,
    )

    if full_reply is None:
        return transcript, None

    return transcript, full_reply


async def process_text_message(
    text: str,
    conversation_id: int,
    voice_id: str,
    voice_model_dir: Path,
    voice_language: str,
    send_message: SendCallback,
    tts_engine: str = "gptsovits",
) -> Optional[str]:
    """
    处理文字输入消息，执行 LLM→TTS 管道（跳过 STT）。
    Process a text input message, executing the LLM→TTS pipeline (skipping STT).

    Args:
        text: 用户文字输入 / User text input
        conversation_id: 对话 ID / Conversation ID
        voice_id: 当前使用的音色 UUID / UUID of the currently selected voice
        voice_model_dir: 音色模型目录 / Voice model directory
        voice_language: 音色语言 / Voice language
        send_message: WebSocket 发送回调 / WebSocket send callback

    Returns:
        str: AI 回复完整文字，失败返回 None / Full AI reply text; None on failure
    """
    logger.info(f"文字消息管道：text='{text[:50]}...' conv={conversation_id}")

    full_reply, _ = await _llm_tts_pipeline(
        user_message=text,
        conversation_id=conversation_id,
        voice_id=voice_id,
        voice_model_dir=voice_model_dir,
        voice_language=voice_language,
        send_message=send_message,
        tts_engine=tts_engine,
    )

    return full_reply


async def _llm_tts_pipeline(
    user_message: str,
    conversation_id: int,
    voice_id: str,
    voice_model_dir: Path,
    voice_language: str,
    send_message: SendCallback,
    tts_engine: str = "gptsovits",
) -> tuple[Optional[str], int]:
    """
    LLM 流式生成 + 并行 TTS 核心管道。
    Core pipeline for LLM streaming generation with parallel TTS.

    延迟优化原理：
    Latency optimization principle:
    - 每当 LLM 输出跨越句子边界，立即 asyncio.create_task 启动该句的 TTS 合成
      Whenever LLM output crosses a sentence boundary, immediately launch TTS synthesis
      for that sentence via asyncio.create_task
    - TTS 合成（asyncio.to_thread）在线程池中运行，与 LLM 继续出 token 并发进行
      TTS synthesis (asyncio.to_thread) runs in a thread pool, concurrent with continued LLM token generation
    - LLM 输出完毕后按 seq 顺序 await 各 TTS 任务，顺序发送音频块
      After LLM output finishes, await TTS tasks in seq order and send audio chunks sequentially
    - 相比旧方案（LLM 全量结束后再逐句 TTS），首句音频延迟可降低 LLM 生成时间
      Compared to the old approach (TTS sentence by sentence after full LLM completion),
      first-sentence audio latency is reduced by the LLM generation time

    Args:
        user_message: 用户输入文字 / User input text
        conversation_id: 对话 ID / Conversation ID
        voice_id: 音色 UUID / Voice UUID
        voice_model_dir: 音色模型目录 / Voice model directory
        voice_language: 语言 / Language
        send_message: WebSocket 发送回调 / WebSocket send callback
        tts_engine: TTS 引擎（"gptsovits" 或 "cosyvoice2"）/ TTS engine ("gptsovits" or "cosyvoice2")

    Returns:
        (full_reply, audio_sent_count)
    """
    full_reply_parts: list[str] = []
    sentence_buffer = ""
    # 每个元素：(seq编号, asyncio.Task[Optional[bytes]])
    # Each element: (seq number, asyncio.Task[Optional[bytes]])
    tts_tasks: list[tuple[int, asyncio.Task]] = []
    seq = 0

    def _make_tts_task(sentence: str) -> asyncio.Task:
        """根据 tts_engine 创建对应的 TTS 异步任务。
        Create the corresponding TTS async task based on tts_engine."""
        if tts_engine == "cosyvoice2":
            return asyncio.create_task(
                synthesize_speech_cosyvoice(
                    text=sentence,
                    voice_id=voice_id,
                    model_dir=voice_model_dir,
                    language=voice_language,
                )
            )
        return asyncio.create_task(
            synthesize_speech(
                text=sentence,
                voice_id=voice_id,
                model_dir=voice_model_dir,
                language=voice_language,
            )
        )

    try:
        async for chunk in stream_chat(
            user_message=user_message,
            conversation_id=conversation_id,
        ):
            # LLM 错误标记：取消所有待完成的 TTS 任务，向客户端发送错误，提前返回
            # LLM error marker: cancel all pending TTS tasks, send error to client, and return early
            if chunk.startswith(LLM_ERROR_MARKER):
                error_text = chunk[len(LLM_ERROR_MARKER):]
                for _, t in tts_tasks:
                    if not t.done():
                        t.cancel()
                await send_message({"type": "error", "message": error_text})
                return None, 0

            full_reply_parts.append(chunk)
            sentence_buffer += chunk
            await send_message({"type": "llm_chunk", "text": chunk})

            # 检测句子边界，对每个完整句子立即启动 TTS 任务
            # Detect sentence boundaries and immediately start a TTS task for each complete sentence
            completed, sentence_buffer = _extract_sentences(sentence_buffer)
            for sentence in completed:
                if sentence.strip():
                    tts_tasks.append((seq, _make_tts_task(sentence.strip())))
                    seq += 1

        # 末尾未以标点结束的最后一段
        # Handle the trailing segment that does not end with punctuation
        if sentence_buffer.strip():
            tts_tasks.append((seq, _make_tts_task(sentence_buffer.strip())))

        full_reply = "".join(full_reply_parts).strip()
        if not full_reply:
            for _, t in tts_tasks:
                t.cancel()
            await send_message({"type": "error", "message": "AI 未返回有效回复"})
            return None, 0

        logger.info(
            f"LLM 完成：'{full_reply[:50]}...'，已创建 {len(tts_tasks)} 个 TTS 任务"
        )

        # 按 seq 顺序等待 TTS 任务并发送音频（保证前端播放顺序）
        # Await TTS tasks in seq order and send audio (guarantees frontend playback order)
        audio_sent = 0
        for s_seq, task in tts_tasks:
            try:
                wav_bytes = await task
            except Exception as e:
                logger.warning(f"TTS 任务[{s_seq}] 异常，跳过：{e}")
                continue
            if wav_bytes:
                audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
                await send_message({
                    "type": "audio_chunk",
                    "data": audio_b64,
                    "seq": s_seq,
                })
                audio_sent += 1
                logger.debug(f"TTS[{s_seq}] 发送：{len(wav_bytes) // 1024}KB")
            else:
                logger.warning(f"TTS 任务[{s_seq}] 合成失败，已跳过")

        if audio_sent == 0 and tts_tasks:
            logger.warning(f"全部 TTS 任务均失败，voice_id={voice_id}")

        return full_reply, audio_sent

    except Exception:
        # 异常时取消所有待完成的 TTS 任务，避免资源泄漏
        # Cancel all pending TTS tasks on exception to prevent resource leaks
        for _, t in tts_tasks:
            if not t.done():
                t.cancel()
        raise
