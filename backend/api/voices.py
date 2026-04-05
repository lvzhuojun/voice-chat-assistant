"""
音色模型管理 API 路由
提供音色的导入、列表、详情、删除、选择和测试接口
"""

import json
import tempfile
from pathlib import Path
from typing import Annotated

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.limiter import limiter

from backend.database import get_db
from backend.models.user import User
from backend.models.voice_model import VoiceModel
from backend.schemas.schemas import (
    VoiceModelResponse,
    VoiceModelListItem,
    VoiceSelectResponse,
    SimpleMessageResponse,
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
@limiter.limit("20/hour")
async def import_voice(
    request: Request,
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

    # 限制上传大小，防止超大文件耗尽内存
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件过大，最大支持 {settings.max_upload_size_mb}MB",
        )

    # 将上传的文件写入临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp_path = Path(tmp.name)
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


@router.get("/current/info", response_model=Optional[VoiceModelListItem])
async def get_current_voice(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[VoiceModelListItem]:
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
        return None

    return VoiceModelListItem.model_validate(voice)


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


@router.delete("/{voice_db_id}", response_model=SimpleMessageResponse)
async def delete_voice(
    voice_db_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimpleMessageResponse:
    """
    删除音色（删除文件 + 数据库记录）。

    Args:
        voice_db_id: 音色数据库 ID
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        SimpleMessageResponse: 操作结果
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
    return SimpleMessageResponse(message="音色已删除")


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


@router.post("/{voice_db_id}/test")
async def test_voice(
    voice_db_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """
    测试音色合成（返回 WAV 音频）。

    合成一句固定测试文字，用于验证音色模型是否可用。
    返回 audio/wav 格式的二进制音频数据。

    Args:
        voice_db_id: 音色数据库 ID
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        WAV 音频文件（Content-Type: audio/wav）
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

    model_dir = Path(voice.gpt_model_path).parent

    from backend.core.tts_engine import synthesize_speech

    test_text = f"你好，我是{voice.voice_name}，这是一段测试语音。"
    wav_bytes = await synthesize_speech(
        text=test_text,
        voice_id=voice.voice_id,
        model_dir=model_dir,
        language=voice.language,
    )

    if wav_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="音色合成失败，请检查模型文件是否完整",
        )

    logger.info(f"用户 {current_user.email} 测试音色：{voice.voice_name}")
    return Response(content=wav_bytes, media_type="audio/wav")
