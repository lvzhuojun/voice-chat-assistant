"""
TTS（文字转语音）引擎模块
严格对接 voice-cloning-service（项目一）的 GPT-SoVITS 模型格式
使用 LRU 缓存最多 3 个音色模型，避免 VRAM 溢出
"""

import io
import sys
import tempfile
from pathlib import Path
from collections import OrderedDict
from typing import Optional

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# TTS 模型缓存上限（最多同时加载 3 个音色，防止 VRAM 溢出）
MAX_CACHED_MODELS = 3

# LRU 缓存：OrderedDict，key = voice_id，value = TTS 实例
# 使用 OrderedDict 实现 LRU（最近最少使用淘汰）
_model_cache: OrderedDict[str, object] = OrderedDict()


def _ensure_gptsovits_in_path() -> bool:
    """
    将 GPT-SoVITS 源码目录加入 sys.path，使 TTS_infer_pack 可导入。
    与项目一保持一致，从 settings.gptsovits_dir 读取路径。

    Returns:
        bool: 路径是否已成功加入
    """
    gptsovits_dir = Path(settings.gptsovits_dir).resolve()
    if not gptsovits_dir.exists():
        logger.error(
            f"GPT-SoVITS 目录不存在：{gptsovits_dir}\n"
            "请先运行 setup/clone_gptsovits.bat 克隆 GPT-SoVITS 源码"
        )
        return False

    gptsovits_str = str(gptsovits_dir)
    if gptsovits_str not in sys.path:
        sys.path.insert(0, gptsovits_str)
        logger.debug(f"已将 GPT-SoVITS 目录加入 sys.path：{gptsovits_str}")

    return True


def _load_tts_model(
    voice_id: str,
    model_dir: Path,
) -> Optional[object]:
    """
    加载单个 GPT-SoVITS TTS 模型。

    严格按照 voice-cloning-service 的加载方式实现：
    使用 TTS_Config "custom" 字段传入所有路径。

    Args:
        voice_id: 音色 UUID
        model_dir: 音色模型目录（storage/voice_models/{user_id}/{voice_id}/）

    Returns:
        TTS 实例，加载失败返回 None
    """
    # 查找模型文件
    gpt_files = list(model_dir.glob(f"*_gpt.ckpt"))
    sovits_files = list(model_dir.glob(f"*_sovits.pth"))

    if not gpt_files:
        logger.error(f"音色 {voice_id} 缺少 _gpt.ckpt 文件，目录：{model_dir}")
        return None
    if not sovits_files:
        logger.error(f"音色 {voice_id} 缺少 _sovits.pth 文件，目录：{model_dir}")
        return None

    gpt_path = str(gpt_files[0])
    sovits_path = str(sovits_files[0])

    try:
        # 确保 GPT-SoVITS 在 sys.path
        if not _ensure_gptsovits_in_path():
            return None

        from TTS_infer_pack.TTS import TTS, TTS_Config

        # 按照项目一的标准加载方式
        config = TTS_Config({
            "custom": {
                "device": "cuda",
                "is_half": True,
                "version": "v2",
                "t2s_weights_path": gpt_path,
                "vits_weights_path": sovits_path,
                "cnhuhbert_base_path": settings.hubert_path,
                "bert_base_path": settings.bert_path,
            }
        })
        tts = TTS(config)
        logger.info(f"TTS 模型加载成功：voice_id={voice_id}")
        return tts

    except ImportError as e:
        logger.error(
            f"无法导入 TTS_infer_pack.TTS：{e}\n"
            "请确保 GPT-SoVITS 目录已克隆且路径正确"
        )
        return None
    except Exception as e:
        logger.error(f"TTS 模型加载失败（voice_id={voice_id}）：{e}")
        return None


def get_tts_model(voice_id: str, model_dir: Path) -> Optional[object]:
    """
    获取 TTS 模型（带 LRU 缓存，最多缓存 3 个）。

    缓存策略：
    - 命中缓存：将该 voice_id 移到末尾（最近使用），直接返回
    - 未命中：加载新模型
      - 若缓存已满（3个）：淘汰最早使用的（OrderedDict 头部）
      - 加载成功后存入缓存

    Args:
        voice_id: 音色 UUID
        model_dir: 音色模型目录

    Returns:
        TTS 实例，失败返回 None
    """
    # 命中缓存
    if voice_id in _model_cache:
        # 移到末尾（标记为最近使用）
        _model_cache.move_to_end(voice_id)
        logger.debug(f"TTS 模型缓存命中：{voice_id}")
        return _model_cache[voice_id]

    # 未命中，加载新模型
    logger.info(f"TTS 模型缓存未命中，开始加载：{voice_id}")

    # 缓存已满，淘汰最旧的
    if len(_model_cache) >= MAX_CACHED_MODELS:
        evicted_id, _ = _model_cache.popitem(last=False)  # 弹出最旧的（头部）
        logger.info(f"TTS 模型缓存已满，淘汰：{evicted_id}（当前缓存数：{len(_model_cache)}）")

    # 加载模型
    tts = _load_tts_model(voice_id, model_dir)
    if tts is None:
        return None

    # 存入缓存
    _model_cache[voice_id] = tts
    logger.info(f"TTS 模型已缓存：{voice_id}（当前缓存数：{len(_model_cache)}）")
    return tts


async def synthesize_speech(
    text: str,
    voice_id: str,
    model_dir: Path,
    language: str = "zh",
    speed_factor: float = 1.0,
    temperature: float = 1.0,
    top_k: int = 5,
    top_p: float = 1.0,
) -> Optional[bytes]:
    """
    使用 GPT-SoVITS 合成语音。

    推理时必须使用 reference.wav 作为音色参考（项目一规范）。

    Args:
        text: 要合成的文字
        voice_id: 音色 UUID
        model_dir: 音色模型目录（含 reference.wav）
        language: 语言（zh/en/auto，默认 zh）
        speed_factor: 语速（1.0 正常，>1 加速，<1 减速）
        temperature: 采样温度
        top_k: Top-K 采样
        top_p: Top-P 采样

    Returns:
        bytes: WAV 格式音频字节流，失败返回 None
    """
    if not text or not text.strip():
        logger.warning("TTS 输入文字为空，跳过合成")
        return None

    # 检查 reference.wav
    ref_audio_path = model_dir / "reference.wav"
    if not ref_audio_path.exists():
        logger.error(f"音色 {voice_id} 缺少 reference.wav，路径：{ref_audio_path}")
        return None

    # 获取 TTS 模型（LRU 缓存）
    tts = get_tts_model(voice_id, model_dir)
    if tts is None:
        logger.error(f"无法加载 TTS 模型：{voice_id}")
        return None

    try:
        # 语言映射（GPT-SoVITS 接受的格式）
        lang_map = {
            "zh": "zh",
            "en": "en",
            "auto": "auto",
            "ja": "ja",
        }
        text_lang = lang_map.get(language.lower(), "zh")

        # 推理参数（与项目一的调用方式一致）
        infer_params = {
            "text": text.strip(),
            "text_lang": text_lang,
            "ref_audio_path": str(ref_audio_path),  # 必须使用 reference.wav
            "prompt_lang": text_lang,
            "prompt_text": "",              # 参考文本（可选，留空使用原始参考音频）
            "top_k": top_k,
            "top_p": top_p,
            "temperature": temperature,
            "text_split_method": "cut5",   # 按标点分割（适合中英文混合）
            "batch_size": 1,
            "speed_factor": speed_factor,
            "fragment_interval": 0.3,      # 分段间隔（秒）
            "streaming_mode": False,       # 非流式，一次返回全部音频
            "seed": -1,                    # 随机种子，-1 表示随机
            "parallel_infer": True,        # 并行推理
            "repetition_penalty": 1.35,    # 重复惩罚（与项目一一致）
        }

        logger.debug(f"TTS 推理：text='{text[:50]}...' lang={text_lang} voice={voice_id}")

        # 执行推理
        result_generator = tts.run(infer_params)

        # 收集所有音频块并合并
        audio_segments = []
        sample_rate = None

        for sr, audio_data in result_generator:
            if sample_rate is None:
                sample_rate = sr
            audio_segments.append(audio_data)

        if not audio_segments:
            logger.error(f"TTS 推理未产生音频：{voice_id}")
            return None

        # 合并音频片段为 WAV bytes
        import numpy as np
        import soundfile as sf

        if len(audio_segments) == 1:
            combined = audio_segments[0]
        else:
            combined = np.concatenate(audio_segments, axis=0)

        # 写入内存缓冲区
        buffer = io.BytesIO()
        sf.write(buffer, combined, sample_rate, format="WAV")
        wav_bytes = buffer.getvalue()

        logger.info(
            f"TTS 合成完成：{len(wav_bytes) // 1024}KB，"
            f"时长约 {len(combined) / sample_rate:.1f}s"
        )
        return wav_bytes

    except Exception as e:
        logger.error(f"TTS 推理失败（voice_id={voice_id}）：{e}", exc_info=True)
        return None


def get_cached_model_count() -> int:
    """
    返回当前 TTS 模型缓存数量。
    用于健康检查接口。

    Returns:
        int: 已缓存的模型数
    """
    return len(_model_cache)


def clear_model_cache() -> None:
    """
    清空 TTS 模型缓存（释放 VRAM）。
    通常不需要手动调用，但在内存紧张时可以调用。
    """
    _model_cache.clear()
    logger.info("TTS 模型缓存已清空")
