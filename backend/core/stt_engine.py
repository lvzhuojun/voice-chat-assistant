"""
STT（语音转文字）引擎模块
STT (Speech-to-Text) engine module.
使用 faster-whisper 进行语音识别，支持中英文自动检测
Uses faster-whisper for speech recognition with automatic Chinese/English detection.
RTX 5060 / CUDA 13.1 / PyTorch 2.7 cu128 兼容
Compatible with RTX 5060 / CUDA 13.1 / PyTorch 2.7 cu128.
"""

import asyncio
import io
import sys
import tempfile
import subprocess
import threading
from pathlib import Path
from typing import Optional

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _find_ffmpeg() -> str:
    """
    查找 ffmpeg 可执行文件路径。
    Locate the ffmpeg executable path.
    优先检查当前 Python 解释器所在 conda 环境的 Library/bin/，
    再尝试系统 PATH。
    First checks Library/bin/ in the conda environment of the current Python interpreter,
    then falls back to the system PATH.
    """
    import shutil
    # conda 环境里 ffmpeg 通常在 {env}/Library/bin/ffmpeg.exe（Windows）
    # In a conda environment, ffmpeg is typically at {env}/Library/bin/ffmpeg.exe (Windows)
    conda_ffmpeg = Path(sys.executable).parent.parent / "Library" / "bin" / "ffmpeg.exe"
    if conda_ffmpeg.exists():
        return str(conda_ffmpeg)
    # 回退到 PATH / Fall back to PATH
    found = shutil.which("ffmpeg")
    if found:
        return found
    return "ffmpeg"  # 让 FileNotFoundError 自然抛出 / Let FileNotFoundError raise naturally

# 全局 WhisperModel 实例（单例，避免重复加载）
# Global WhisperModel instance (singleton, avoids repeated loading)
_whisper_model = None
_whisper_load_lock = threading.Lock()


def get_whisper_model():
    """
    获取 WhisperModel 单例（线程安全）。
    Retrieve the WhisperModel singleton (thread-safe).
    首次调用时加载模型，后续直接返回缓存实例。
    Loads the model on the first call; returns the cached instance on subsequent calls.
    使用双重检查锁定（double-checked locking）避免并发时重复加载。
    Uses double-checked locking to prevent duplicate loading under concurrency.

    Returns:
        WhisperModel: faster-whisper 模型实例，加载失败返回 None
        / faster-whisper model instance; None if loading fails
    """
    global _whisper_model

    if _whisper_model is not None:
        return _whisper_model

    with _whisper_load_lock:
        # 再次检查：防止其他线程在等待锁期间已完成加载
        # Re-check: prevents duplicate loading by threads that waited for the lock
        if _whisper_model is not None:
            return _whisper_model

        try:
            from faster_whisper import WhisperModel

            model_size = settings.whisper_model_size
            device = settings.whisper_device

            logger.info(f"加载 Whisper 模型：{model_size}，设备：{device}")

            # compute_type:
            # - CUDA + float16：RTX 系列推荐，速度快
            #   Recommended for RTX series on CUDA; fast inference
            # - CUDA + int8_float16：显存不足时备选
            #   Alternative when VRAM is insufficient on CUDA
            # - cpu + int8：CPU 推理
            #   CPU inference
            compute_type = "float16" if device == "cuda" else "int8"

            _whisper_model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                # 下载/加载模型的路径，使用 HuggingFace 缓存默认位置
                # Path for downloading/loading the model; uses the default HuggingFace cache location
                download_root=None,
            )

            logger.info(f"Whisper 模型加载成功：{model_size} on {device}")
            return _whisper_model

        except Exception as e:
            logger.error(f"Whisper 模型加载失败：{e}")
            logger.error("请检查：1. CUDA 是否可用  2. faster-whisper 是否安装")
            return None


async def convert_audio_to_wav(audio_bytes: bytes, input_format: str = "webm") -> Optional[bytes]:
    """
    使用 FFmpeg 将音频字节流转换为 WAV 格式。
    Convert an audio byte stream to WAV format using FFmpeg.
    浏览器 MediaRecorder 默认输出 WebM/Opus，需要转换。
    Browser MediaRecorder outputs WebM/Opus by default, which requires conversion.

    Args:
        audio_bytes: 输入音频字节流 / Input audio byte stream
        input_format: 输入格式（webm/ogg/mp4 等）/ Input format (webm/ogg/mp4, etc.)

    Returns:
        bytes: WAV 格式音频字节流，失败返回 None / WAV-format audio byte stream; None on failure
    """
    inp_path: Path | None = None
    out_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{input_format}", delete=False) as inp:
            inp_path = Path(inp.name)
            inp.write(audio_bytes)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out:
            out_path = Path(out.name)

        # 使用 FFmpeg 转换
        # Convert using FFmpeg
        # -ar 16000：采样率 16kHz（Whisper 最优）/ Sample rate 16kHz (optimal for Whisper)
        # -ac 1：单声道 / Mono channel
        # -f wav：输出 WAV 格式 / Output WAV format
        ffmpeg_bin = _find_ffmpeg()
        cmd = [
            ffmpeg_bin,
            "-y",                    # 覆盖输出文件 / Overwrite output file
            "-i", str(inp_path),     # 输入文件 / Input file
            "-ar", "16000",          # 采样率 16kHz / Sample rate 16kHz
            "-ac", "1",              # 单声道 / Mono channel
            "-f", "wav",             # 输出格式 / Output format
            str(out_path),
        ]

        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg 转换失败：{result.stderr.decode('utf-8', errors='replace')}")
            return None

        with open(out_path, "rb") as f:
            wav_bytes = f.read()

        return wav_bytes

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg 转换超时（>30s）")
        return None
    except FileNotFoundError:
        logger.error("未找到 FFmpeg，请安装：conda install -c conda-forge ffmpeg")
        return None
    except Exception as e:
        logger.error(f"音频转换失败：{e}")
        return None
    finally:
        # 清理临时文件 / Clean up temporary files
        try:
            if inp_path is not None and inp_path.exists():
                inp_path.unlink()
            if out_path is not None and out_path.exists():
                out_path.unlink()
        except Exception:
            pass


async def transcribe_audio(
    audio_bytes: bytes,
    audio_format: str = "webm",
    language: Optional[str] = None,
) -> Optional[str]:
    """
    将音频转写为文字。
    Transcribe audio to text.

    流程：
    Workflow:
    1. WebM → WAV（FFmpeg）/ Convert WebM to WAV (FFmpeg)
    2. 使用 faster-whisper 转写 / Transcribe using faster-whisper
    3. 合并所有分段文字 / Merge all segment texts

    Args:
        audio_bytes: 音频字节流（WebM/WAV 等）/ Audio byte stream (WebM/WAV, etc.)
        audio_format: 音频格式（默认 webm）/ Audio format (default: webm)
        language: 指定语言（None 则自动检测，支持 zh/en 等）
                  / Specify language (None for auto-detection; supports zh/en, etc.)

    Returns:
        str: 识别出的文字，失败返回 None / Recognized text; None on failure
    """
    model = get_whisper_model()
    if model is None:
        logger.error("Whisper 模型未加载，无法转写")
        return None

    # 如果不是 WAV，先转换 / Convert to WAV first if not already in WAV format
    if audio_format.lower() not in ("wav",):
        logger.debug(f"转换音频格式：{audio_format} → WAV")
        wav_bytes = await convert_audio_to_wav(audio_bytes, input_format=audio_format)
        if wav_bytes is None:
            logger.error("音频格式转换失败")
            return None
    else:
        wav_bytes = audio_bytes

    # 将 WAV bytes 写入临时文件（faster-whisper 需要文件路径）
    # Write WAV bytes to a temporary file (faster-whisper requires a file path)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(wav_bytes)

    def _run_transcribe() -> Optional[str]:
        """在线程池中执行阻塞的 Whisper 推理，避免占用 asyncio 事件循环。
        Execute blocking Whisper inference in a thread pool to avoid blocking the asyncio event loop."""
        try:
            # 转写参数
            # Transcription parameters
            # - beam_size=5：束搜索宽度，5 是精度和速度的平衡点
            #   Beam search width; 5 is a good balance between accuracy and speed
            # - language=None：自动检测语言（支持中英文混合）
            #   Auto-detect language (supports Chinese/English mixed input)
            # - vad_filter=True：语音活动检测，过滤静音段
            #   Voice activity detection to filter out silent segments
            segments, info = model.transcribe(
                str(tmp_path),
                beam_size=5,
                language=language,  # None 时自动检测 / Auto-detect when None
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            detected_lang = info.language
            logger.debug(f"检测到语言：{detected_lang}（置信度：{info.language_probability:.2f}）")

            # 合并所有分段（中文不加空格，各分段 strip 后直接拼接）
            # Merge all segments (no space added for Chinese; each segment is stripped then concatenated)
            text_parts = [s.text.strip() for s in segments if s.text.strip()]
            full_text = "".join(text_parts).strip()
            logger.info(f"STT 识别结果：{full_text[:100]}...")
            return full_text if full_text else None
        except Exception as e:
            logger.error(f"Whisper 转写失败：{e}")
            return None

    try:
        return await asyncio.to_thread(_run_transcribe)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def is_whisper_loaded() -> bool:
    """
    检查 Whisper 模型是否已加载。
    Check whether the Whisper model has been loaded.

    Returns:
        bool: 是否已加载 / Whether the model is loaded
    """
    return _whisper_model is not None
