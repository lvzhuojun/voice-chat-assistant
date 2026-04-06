"""
CosyVoice 2 TTS 引擎模块
使用单一共享基础模型 + 参考音频（reference.wav）实现零样本语音克隆。

与 GPT-SoVITS 不同，CosyVoice 2 不需要针对每个音色训练专属模型，
只需一个参考音频片段即可克隆音色，延迟更低、部署更简便。

模型加载策略：
- CosyVoice2 基础模型全局单例（线程安全懒加载）
- 每个 voice_id 的 speaker prompt（参考音频 tensor）独立缓存，避免重复 I/O
"""

import asyncio
import io
import sys
import threading
from pathlib import Path
from typing import Optional

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ── 全局模型单例 ──────────────────────────────────────────────────────────────
_cosyvoice_model = None
_model_load_lock = threading.Lock()

# ── 参考音频缓存（key: voice_id, value: (prompt_speech_16k, prompt_text)） ────
_speaker_cache: dict[str, tuple] = {}
_speaker_cache_lock = threading.Lock()


def _ensure_cosyvoice_in_path() -> bool:
    """
    将 CosyVoice 源码目录及其依赖加入 sys.path。

    CosyVoice 仓库结构：
      CosyVoice/
        cosyvoice/        <- 主包
        third_party/
          Matcha-TTS/     <- 依赖

    Returns:
        bool: 目录是否存在
    """
    cosyvoice_dir = Path(settings.cosyvoice_dir).resolve()
    if not cosyvoice_dir.exists():
        logger.error(
            f"CosyVoice 目录不存在：{cosyvoice_dir}\n"
            "请先克隆 CosyVoice 仓库并下载 CosyVoice2-0.5B 预训练模型"
        )
        return False

    cosyvoice_str = str(cosyvoice_dir)
    if cosyvoice_str not in sys.path:
        sys.path.insert(0, cosyvoice_str)
        logger.debug(f"已将 CosyVoice 目录加入 sys.path：{cosyvoice_str}")

    matcha_dir = cosyvoice_dir / "third_party" / "Matcha-TTS"
    if matcha_dir.exists():
        matcha_str = str(matcha_dir)
        if matcha_str not in sys.path:
            sys.path.insert(0, matcha_str)
            logger.debug(f"已将 Matcha-TTS 加入 sys.path：{matcha_str}")

    return True


def _get_cosyvoice_model():
    """
    获取 CosyVoice2 模型单例（线程安全双重检查懒加载）。

    Returns:
        CosyVoice2 实例，失败返回 None
    """
    global _cosyvoice_model
    if _cosyvoice_model is not None:
        return _cosyvoice_model

    with _model_load_lock:
        if _cosyvoice_model is not None:
            return _cosyvoice_model

        if not _ensure_cosyvoice_in_path():
            return None

        try:
            from cosyvoice.cli.cosyvoice import CosyVoice2  # type: ignore

            model_path = str(
                Path(settings.cosyvoice_dir).resolve()
                / "pretrained_models"
                / "CosyVoice2-0.5B"
            )
            logger.info(f"加载 CosyVoice2 模型：{model_path}")
            _cosyvoice_model = CosyVoice2(model_path, load_jit=True, load_trt=False)
            logger.info("CosyVoice2 模型加载成功")
        except ImportError as e:
            logger.error(
                f"无法导入 cosyvoice：{e}\n"
                "请确认 CosyVoice 仓库已克隆，且依赖已安装（pip install -r CosyVoice/requirements.txt）"
            )
            return None
        except Exception as e:
            logger.error(f"CosyVoice2 模型加载失败：{e}", exc_info=True)
            return None

    return _cosyvoice_model


def _load_speaker_prompt(voice_id: str, model_dir: Path) -> Optional[tuple]:
    """
    加载音色参考音频作为 speaker prompt，并缓存。
    第一次调用时从磁盘加载并转为 16kHz tensor，后续复用缓存。

    Args:
        voice_id: 音色 UUID（缓存键）
        model_dir: 音色目录（含 reference.wav）

    Returns:
        (prompt_speech_16k, prompt_text) 或 None
    """
    with _speaker_cache_lock:
        if voice_id in _speaker_cache:
            return _speaker_cache[voice_id]

    ref_wav = model_dir / "reference.wav"
    if not ref_wav.exists():
        logger.error(f"CosyVoice 音色缺少 reference.wav：{ref_wav}")
        return None

    try:
        from cosyvoice.utils.file_utils import load_wav  # type: ignore

        prompt_speech_16k = load_wav(str(ref_wav), 16000)
        # prompt_text 为参考音频的文字转录；留空时 CosyVoice2 仍可正常工作
        # 如果 metadata.json 中提供了 reference_text 字段，可在此读取以提升相似度
        prompt_text = ""

        with _speaker_cache_lock:
            # 二次检查防止并发写入
            if voice_id not in _speaker_cache:
                _speaker_cache[voice_id] = (prompt_speech_16k, prompt_text)
        logger.info(f"CosyVoice2 音色 prompt 已缓存：{voice_id}")
        return prompt_speech_16k, prompt_text

    except Exception as e:
        logger.error(f"加载 CosyVoice2 speaker prompt 失败（{voice_id}）：{e}", exc_info=True)
        return None


async def synthesize_speech_cosyvoice(
    text: str,
    voice_id: str,
    model_dir: Path,
    language: str = "zh",
    speed_factor: float = 1.0,
) -> Optional[bytes]:
    """
    使用 CosyVoice 2 零样本语音克隆合成语音。

    推理在线程池中执行（asyncio.to_thread），不阻塞事件循环。

    Args:
        text: 要合成的文字
        voice_id: 音色 UUID
        model_dir: 音色目录（含 reference.wav）
        language: 语言（当前版本 CosyVoice2 自动检测，参数保留兼容性）
        speed_factor: 语速倍率（0.5~2.0）

    Returns:
        WAV 格式字节流，失败返回 None
    """
    if not text or not text.strip():
        logger.warning("CosyVoice2 输入文字为空，跳过合成")
        return None

    def _run_inference() -> Optional[bytes]:
        model = _get_cosyvoice_model()
        if model is None:
            return None

        prompt = _load_speaker_prompt(voice_id, model_dir)
        if prompt is None:
            return None

        prompt_speech_16k, prompt_text = prompt

        try:
            import numpy as np
            import soundfile as sf

            audio_chunks = []
            for result in model.inference_zero_shot(
                tts_text=text.strip(),
                prompt_text=prompt_text,
                prompt_speech_16k=prompt_speech_16k,
                stream=False,
                speed=speed_factor,
            ):
                chunk = result["tts_speech"].squeeze().numpy()
                audio_chunks.append(chunk)

            if not audio_chunks:
                logger.error(f"CosyVoice2 未产生音频输出：voice_id={voice_id}")
                return None

            combined = (
                audio_chunks[0]
                if len(audio_chunks) == 1
                else np.concatenate(audio_chunks)
            )
            sample_rate = model.sample_rate

            buffer = io.BytesIO()
            sf.write(buffer, combined, sample_rate, format="WAV")
            wav_bytes = buffer.getvalue()

            logger.info(
                f"CosyVoice2 合成完成：{len(wav_bytes) // 1024}KB，"
                f"时长约 {len(combined) / sample_rate:.1f}s"
            )
            return wav_bytes

        except Exception as e:
            logger.error(f"CosyVoice2 推理失败（voice_id={voice_id}）：{e}", exc_info=True)
            return None

    try:
        return await asyncio.to_thread(_run_inference)
    except Exception as e:
        logger.error(f"CosyVoice2 线程调度失败（voice_id={voice_id}）：{e}", exc_info=True)
        return None


def is_cosyvoice_available() -> bool:
    """
    检查 CosyVoice 目录是否存在（快速检查，不尝试导入模型）。
    用于健康检查和 UI 提示。
    """
    return Path(settings.cosyvoice_dir).resolve().exists()


def get_speaker_cache_count() -> int:
    """返回当前缓存的 speaker prompt 数量（用于监控）。"""
    return len(_speaker_cache)


def clear_speaker_cache() -> None:
    """清空 speaker prompt 缓存（释放内存）。"""
    with _speaker_cache_lock:
        _speaker_cache.clear()
    logger.info("CosyVoice2 speaker prompt 缓存已清空")
