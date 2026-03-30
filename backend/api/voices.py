"""
音色模型管理 API 路由
提供音色的导入、列表、详情、删除和选择接口
"""

import json
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models.user import User
from backend.models.voice_model import VoiceModel
from backend.schemas.schemas import (
    VoiceModelResponse,
    VoiceModelListItem,
    VoiceSelectResponse,
    MessageResponse_Simple,
)
from backend.core.security import get_current_user
from backend.config import get_settings
from backend.utils.file_utils import (
    validate_voice_zip,
    extract_voice_zip,
    get_voice_model_dir,
    delete_voice_model_dir,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/voices", tags=["音色管理"])


# Redis 客户端（懒加载，避免启动时连接失败）
_redis_client = None


async def get_redis():
    """
    获取 Redis 客户端（单例）。
    如果 Redis 不可用，返回 None，相关功能降级处理。
    """
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as redis
            _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            await _redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.warning(f"Redis 连接失败，将不缓存音色选择：{e}")
            _redis_client = None
    return _redis_client


@router.post("/import", response_model=VoiceModelResponse, status_code=status.HTTP_201_CREATED)
async def import_voice(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(..., description="音色 ZIP 包"),
) -> VoiceModelResponse:
    """
    导入音色模型（上传 ZIP 包）。

    ZIP 包必须包含：
    - {voice_id}_gpt.ckpt
    - {voice_id}_sovits.pth
    - metadata.json
    - reference.wav

    处理流程：
    1. 验证 ZIP 格式和文件完整性
    2. 解压到 storage/voice_models/{user_id}/{voice_id}/
    3. 写入数据库

    Args:
        current_user: 当前登录用户
        db: 数据库会话
        file: 上传的 ZIP 文件

    Returns:
        VoiceModelResponse: 创建的音色信息
    """
    # 验证文件类型
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 ZIP 格式文件",
        )

    # 将上传的文件写入临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        # 验证 ZIP 内容
        is_valid, result_msg, metadata = validate_voice_zip(tmp_path)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ZIP 包验证失败：{result_msg}",
            )

        voice_id = result_msg  # validate 成功时返回 voice_id

        # 检查此音色是否已导入（同一用户）
        existing = await db.execute(
            select(VoiceModel).where(
                VoiceModel.user_id == current_user.id,
                VoiceModel.voice_id == voice_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"音色 {voice_id} 已存在，请删除后重新导入",
            )

        # 解压到目标目录
        target_dir = get_voice_model_dir(
            settings.voice_models_path,
            current_user.id,
            voice_id,
        )
        paths = extract_voice_zip(tmp_path, target_dir, voice_id)

        # 从 metadata 获取信息
        voice_name = metadata.get("voice_name", "未命名音色")
        language = metadata.get("language", "zh")

        # 写入数据库
        voice_model = VoiceModel(
            user_id=current_user.id,
            voice_id=voice_id,
            voice_name=voice_name,
            language=language,
            gpt_model_path=paths.get("gpt_model_path", ""),
            sovits_model_path=paths.get("sovits_model_path", ""),
            reference_wav_path=paths.get("reference_wav_path", ""),
            metadata_json=metadata,
            is_active=True,
        )
        db.add(voice_model)
        await db.commit()
        await db.refresh(voice_model)

        logger.info(
            f"用户 {current_user.email} 导入音色：{voice_name} ({voice_id})"
        )
        return VoiceModelResponse.model_validate(voice_model)

    finally:
        # 清理临时文件
        if tmp_path.exists():
            tmp_path.unlink()


@router.get("", response_model=list[VoiceModelListItem])
async def list_voices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[VoiceModelListItem]:
    """
    获取当前用户的音色列表。

    Args:
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        list[VoiceModelListItem]: 音色列表（按创建时间倒序）
    """
    result = await db.execute(
        select(VoiceModel)
        .where(VoiceModel.user_id == current_user.id, VoiceModel.is_active == True)
        .order_by(VoiceModel.created_at.desc())
    )
    voices = result.scalars().all()
    return [VoiceModelListItem.model_validate(v) for v in voices]


@router.get("/{voice_db_id}", response_model=VoiceModelResponse)
async def get_voice(
    voice_db_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VoiceModelResponse:
    """
    获取音色详情。

    Args:
        voice_db_id: 音色数据库 ID
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        VoiceModelResponse: 音色详情
    """
    result = await db.execute(
        select(VoiceModel).where(
            VoiceModel.id == voice_db_id,
            VoiceModel.user_id == current_user.id,
        )
    )
    voice = result.scalar_one_or_none()
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="音色不存在或无权访问",
        )
    return VoiceModelResponse.model_validate(voice)


@router.delete("/{voice_db_id}", response_model=MessageResponse_Simple)
async def delete_voice(
    voice_db_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse_Simple:
    """
    删除音色（删除文件 + 数据库记录）。

    Args:
        voice_db_id: 音色数据库 ID
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        MessageResponse_Simple: 操作结果
    """
    result = await db.execute(
        select(VoiceModel).where(
            VoiceModel.id == voice_db_id,
            VoiceModel.user_id == current_user.id,
        )
    )
    voice = result.scalar_one_or_none()
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="音色不存在或无权访问",
        )

    # 删除文件目录
    model_dir = get_voice_model_dir(
        settings.voice_models_path,
        current_user.id,
        voice.voice_id,
    )
    delete_voice_model_dir(model_dir)

    # 清除 Redis 中的当前音色选择（如果是这个音色）
    redis = await get_redis()
    if redis:
        try:
            current_voice_key = f"user:{current_user.id}:current_voice"
            current_voice = await redis.get(current_voice_key)
            if current_voice == voice.voice_id:
                await redis.delete(current_voice_key)
        except Exception as e:
            logger.warning(f"清除 Redis 音色缓存失败：{e}")

    # 删除数据库记录
    await db.delete(voice)
    await db.commit()

    logger.info(f"用户 {current_user.email} 删除音色：{voice.voice_name} ({voice.voice_id})")
    return MessageResponse_Simple(message="音色已删除")


@router.post("/{voice_db_id}/select", response_model=VoiceSelectResponse)
async def select_voice(
    voice_db_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VoiceSelectResponse:
    """
    设置当前使用的音色（存入 Redis）。
    Redis 不可用时降级为只返回成功响应。

    Args:
        voice_db_id: 音色数据库 ID
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        VoiceSelectResponse: 操作结果
    """
    result = await db.execute(
        select(VoiceModel).where(
            VoiceModel.id == voice_db_id,
            VoiceModel.user_id == current_user.id,
            VoiceModel.is_active == True,
        )
    )
    voice = result.scalar_one_or_none()
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="音色不存在或无权访问",
        )

    # 存入 Redis（Key: user:{user_id}:current_voice，Value: voice_id）
    redis = await get_redis()
    if redis:
        try:
            key = f"user:{current_user.id}:current_voice"
            # 永不过期（用户主动选择）
            await redis.set(key, voice.voice_id)
            logger.info(f"用户 {current_user.email} 设置当前音色：{voice.voice_name}")
        except Exception as e:
            logger.warning(f"Redis 存储当前音色失败：{e}")

    return VoiceSelectResponse(
        message=f"已设置音色：{voice.voice_name}",
        voice_id=voice.voice_id,
    )


@router.get("/current/info", response_model=VoiceModelListItem)
async def get_current_voice(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VoiceModelListItem:
    """
    获取当前用户选择的音色信息。
    从 Redis 读取 voice_id，再查询数据库。

    Args:
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        VoiceModelListItem: 当前音色信息
    """
    # 从 Redis 获取当前音色 ID
    redis = await get_redis()
    voice_id = None
    if redis:
        try:
            key = f"user:{current_user.id}:current_voice"
            voice_id = await redis.get(key)
        except Exception as e:
            logger.warning(f"Redis 读取当前音色失败：{e}")

    if not voice_id:
        # 没有选择，返回第一个可用音色
        result = await db.execute(
            select(VoiceModel)
            .where(VoiceModel.user_id == current_user.id, VoiceModel.is_active == True)
            .order_by(VoiceModel.created_at.desc())
            .limit(1)
        )
        voice = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(VoiceModel).where(
                VoiceModel.voice_id == voice_id,
                VoiceModel.user_id == current_user.id,
            )
        )
        voice = result.scalar_one_or_none()

    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有可用的音色，请先导入音色",
        )

    return VoiceModelListItem.model_validate(voice)
