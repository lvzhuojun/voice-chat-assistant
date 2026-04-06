"""
文件工具模块
处理音色 ZIP 包的解压验证、路径生成等文件操作
File utility module.
Handles voice package ZIP extraction, validation, and path resolution.
"""

import os
import re
import json
import zipfile
import shutil
from pathlib import Path
from typing import Optional

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# voice_id 合法字符：仅允许 UUID / slug 格式，阻止路径穿越
# Allowed characters for voice_id: UUID/slug only, prevents path traversal
_SAFE_VOICE_ID_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,128}$')

# ZIP bomb 防护：解压后总大小上限（500 MB）
# ZIP bomb protection: maximum total uncompressed size (500 MB)
_MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024

# ZIP 包中必须包含的文件后缀 / Required file suffixes that must be present in the ZIP archive
REQUIRED_FILE_SUFFIXES = {
    "_gpt.ckpt",
    "_sovits.pth",
}
REQUIRED_FILES = {
    "metadata.json",
    "reference.wav",
}


def validate_voice_zip(zip_path: Path) -> tuple[bool, str, Optional[dict]]:
    """
    验证上传的音色 ZIP 包是否合法。
    Validate an uploaded voice model ZIP archive.

    验证规则：
    1. 必须包含 metadata.json 和 reference.wav
    2. 必须包含以 _gpt.ckpt 和 _sovits.pth 结尾的模型文件
    3. metadata.json 必须包含 voice_id 字段
    4. base_model_version 必须是 GPT-SoVITS v2

    Validation rules:
    1. Must contain metadata.json and reference.wav
    2. Must contain model files ending with _gpt.ckpt and _sovits.pth
    3. metadata.json must include a voice_id field
    4. base_model_version must be GPT-SoVITS v2

    Args:
        zip_path: ZIP 文件路径 / Path to the ZIP archive

    Returns:
        (是否合法, 错误信息/voice_id, metadata 字典)
        / (is_valid, error_message_or_voice_id, metadata_dict)
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # ZIP bomb 防护：累加解压后大小，超限直接拒绝
            # ZIP bomb protection: accumulate uncompressed sizes and reject if over limit
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > _MAX_UNCOMPRESSED_BYTES:
                return False, (
                    f"ZIP 解压后总大小 {total_uncompressed // 1024 // 1024}MB"
                    f" 超过上限 {_MAX_UNCOMPRESSED_BYTES // 1024 // 1024}MB"
                ), None

            # 获取所有文件名（去除目录前缀，只保留文件名部分）
            # Collect all entry basenames, excluding directory entries
            names = [
                os.path.basename(name)
                for name in zf.namelist()
                if not name.endswith("/")
            ]
            names_set = set(names)

            # 检查 metadata.json 和 reference.wav
            # Verify that all required files are present
            for required in REQUIRED_FILES:
                if required not in names_set:
                    return False, f"ZIP 中缺少必要文件：{required}", None

            # 读取并解析 metadata.json
            # 支持根目录或子目录
            # Read and parse metadata.json, supporting both root-level and nested paths
            metadata_member = next(
                (m for m in zf.namelist() if os.path.basename(m) == "metadata.json"),
                None,
            )
            if not metadata_member:
                return False, "无法找到 metadata.json", None

            with zf.open(metadata_member) as f:
                metadata = json.loads(f.read().decode("utf-8"))

            # 检查必要字段 / Verify that the required voice_id field exists
            if "voice_id" not in metadata:
                return False, "metadata.json 缺少 voice_id 字段", None

            voice_id = metadata["voice_id"]

            # 路径穿越防护：voice_id 只允许安全字符
            # Path traversal protection: voice_id must contain only safe characters
            if not _SAFE_VOICE_ID_RE.match(str(voice_id)):
                return False, (
                    "voice_id 包含非法字符，只允许字母、数字、连字符和下划线"
                ), None

            # 检查模型版本 / Check base model version compatibility
            base_version = metadata.get("base_model_version", "")
            if base_version and "GPT-SoVITS v2" not in base_version:
                logger.warning(f"音色 {voice_id} 版本为 {base_version}，可能不兼容")

            # 检查 GPT 和 SoVITS 模型文件 / Verify GPT and SoVITS model files are present
            has_gpt = any(n.endswith("_gpt.ckpt") for n in names)
            has_sovits = any(n.endswith("_sovits.pth") for n in names)

            if not has_gpt:
                return False, "ZIP 中缺少 _gpt.ckpt 模型文件", None
            if not has_sovits:
                return False, "ZIP 中缺少 _sovits.pth 模型文件", None

            return True, voice_id, metadata

    except zipfile.BadZipFile:
        return False, "上传的文件不是有效的 ZIP 格式", None
    except json.JSONDecodeError:
        return False, "metadata.json 格式错误，无法解析 JSON", None
    except Exception as e:
        logger.error(f"验证 ZIP 包时发生错误: {e}")
        return False, f"验证失败：{str(e)}", None


def validate_voice_zip_cosyvoice(zip_path: Path) -> tuple[bool, str, Optional[dict]]:
    """
    验证 CosyVoice 2 音色 ZIP 包（只需 reference.wav + metadata.json，无需模型文件）。
    Validate a CosyVoice 2 voice ZIP archive (requires only reference.wav + metadata.json,
    no model weight files needed).

    验证规则：
    1. 必须包含 metadata.json 和 reference.wav
    2. metadata.json 必须包含 voice_id 字段
    3. 不要求 _gpt.ckpt / _sovits.pth

    Validation rules:
    1. Must contain metadata.json and reference.wav
    2. metadata.json must include a voice_id field
    3. _gpt.ckpt / _sovits.pth model files are not required

    Args:
        zip_path: ZIP 文件路径 / Path to the ZIP archive

    Returns:
        (是否合法, 错误信息/voice_id, metadata 字典)
        / (is_valid, error_message_or_voice_id, metadata_dict)
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # ZIP bomb 防护 / ZIP bomb protection
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > _MAX_UNCOMPRESSED_BYTES:
                return False, (
                    f"ZIP 解压后总大小 {total_uncompressed // 1024 // 1024}MB"
                    f" 超过上限 {_MAX_UNCOMPRESSED_BYTES // 1024 // 1024}MB"
                ), None

            names = [
                os.path.basename(name)
                for name in zf.namelist()
                if not name.endswith("/")
            ]
            names_set = set(names)

            for required in REQUIRED_FILES:
                if required not in names_set:
                    return False, f"ZIP 中缺少必要文件：{required}", None

            metadata_member = next(
                (m for m in zf.namelist() if os.path.basename(m) == "metadata.json"),
                None,
            )
            if not metadata_member:
                return False, "无法找到 metadata.json", None

            with zf.open(metadata_member) as f:
                metadata = json.loads(f.read().decode("utf-8"))

            if "voice_id" not in metadata:
                return False, "metadata.json 缺少 voice_id 字段", None

            voice_id = metadata["voice_id"]

            # 路径穿越防护 / Path traversal protection
            if not _SAFE_VOICE_ID_RE.match(str(voice_id)):
                return False, (
                    "voice_id 包含非法字符，只允许字母、数字、连字符和下划线"
                ), None

            return True, voice_id, metadata

    except zipfile.BadZipFile:
        return False, "上传的文件不是有效的 ZIP 格式", None
    except json.JSONDecodeError:
        return False, "metadata.json 格式错误，无法解析 JSON", None
    except Exception as e:
        logger.error(f"验证 CosyVoice ZIP 包时发生错误: {e}")
        return False, f"验证失败：{str(e)}", None


def extract_voice_zip(
    zip_path: Path,
    target_dir: Path,
    voice_id: str,
) -> dict[str, str]:
    """
    解压音色 ZIP 包到目标目录，返回各文件的实际路径。
    Extract a voice model ZIP archive into the target directory and return
    the resolved paths for each extracted file.

    Args:
        zip_path: ZIP 文件路径 / Path to the ZIP archive
        target_dir: 目标目录（storage/voice_models/{user_id}/{voice_id}/）
                    / Destination directory (storage/voice_models/{user_id}/{voice_id}/)
        voice_id: 音色 ID / Voice model identifier

    Returns:
        dict: {
            "gpt_model_path": str,
            "sovits_model_path": str,
            "reference_wav_path": str,
            "metadata_json_path": str,
        }
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            if member.endswith("/"):
                continue  # 跳过目录条目 / Skip directory entries

            basename = os.path.basename(member)
            dest_path = target_dir / basename

            # 解压文件 / Extract the file to the destination path
            with zf.open(member) as src, open(dest_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            logger.debug(f"解压：{basename} -> {dest_path}")

            # 记录路径 / Record the resolved path for each known file type
            if basename.endswith("_gpt.ckpt"):
                paths["gpt_model_path"] = str(dest_path)
            elif basename.endswith("_sovits.pth"):
                paths["sovits_model_path"] = str(dest_path)
            elif basename == "reference.wav":
                paths["reference_wav_path"] = str(dest_path)
            elif basename == "metadata.json":
                paths["metadata_json_path"] = str(dest_path)

    logger.info(f"音色 {voice_id} 解压完成，目标目录：{target_dir}")
    return paths


def get_voice_model_dir(base_dir: Path, user_id: int, voice_id: str) -> Path:
    """
    获取音色模型的存储目录路径。
    Resolve the storage directory path for a given voice model.

    Args:
        base_dir: storage/voice_models 根目录 / Root directory for voice model storage
        user_id: 用户 ID / User identifier
        voice_id: 音色 UUID / Voice model UUID

    Returns:
        Path: storage/voice_models/{user_id}/{voice_id}/
    """
    return base_dir / str(user_id) / voice_id


def delete_voice_model_dir(model_dir: Path) -> bool:
    """
    删除音色模型目录（包含所有文件）。
    Delete a voice model directory and all its contents.

    Args:
        model_dir: 要删除的目录 / Directory to delete

    Returns:
        bool: 是否成功删除 / True if deletion succeeded, False otherwise
    """
    try:
        if model_dir.exists():
            shutil.rmtree(model_dir)
            logger.info(f"已删除音色目录：{model_dir}")
        return True
    except Exception as e:
        logger.error(f"删除音色目录失败：{model_dir}, 错误：{e}")
        return False
