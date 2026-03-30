"""
FastAPI 应用主入口
整合所有路由、中间件、启动/关闭逻辑
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理。

    启动时：
    - 创建必要目录
    - 预加载 Whisper 模型（避免首次请求时的冷启动延迟）
    - 检查 GPT-SoVITS 目录

    关闭时：
    - 清理 TTS 模型缓存（释放 VRAM）
    """
    # ── 启动阶段 ──────────────────────────────────────────────
    logger.info("Voice Chat Assistant 后端启动中...")

    # 创建必要的存储目录
    dirs_to_create = [
        settings.storage_path,
        settings.voice_models_path,
        settings.storage_path / "audio",
        Path("logs"),
    ]
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)
        logger.debug(f"目录已就绪：{d}")

    # 预加载 Whisper 模型
    logger.info(f"预加载 Whisper 模型：{settings.whisper_model_size} ({settings.whisper_device})")
    try:
        from backend.core.stt_engine import get_whisper_model
        model = get_whisper_model()
        if model:
            logger.info("Whisper 模型加载成功")
        else:
            logger.warning("Whisper 模型加载失败，STT 功能将不可用")
    except Exception as e:
        logger.error(f"Whisper 预加载异常：{e}")

    # 检查 GPT-SoVITS 目录
    gptsovits_dir = Path(settings.gptsovits_dir)
    if gptsovits_dir.exists():
        logger.info(f"GPT-SoVITS 目录已就绪：{gptsovits_dir}")
    else:
        logger.warning(
            f"GPT-SoVITS 目录不存在：{gptsovits_dir}\n"
            "TTS 功能将不可用，请运行 setup/clone_gptsovits.bat"
        )

    logger.info("Voice Chat Assistant 启动完成")
    logger.info(f"API 文档：http://{settings.host}:{settings.backend_port}/docs")

    yield  # 应用运行中

    # ── 关闭阶段 ──────────────────────────────────────────────
    logger.info("Voice Chat Assistant 正在关闭...")

    # 清理 TTS 模型缓存（释放 VRAM）
    try:
        from backend.core.tts_engine import clear_model_cache
        clear_model_cache()
        logger.info("TTS 模型缓存已释放")
    except Exception as e:
        logger.warning(f"TTS 缓存清理失败：{e}")

    logger.info("Voice Chat Assistant 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="Voice Chat Assistant API",
    description="基于 GPT-SoVITS 的语音对话助手后端 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS 配置 ─────────────────────────────────────────────────
# 允许前端开发服务器访问
CORS_ORIGINS = [
    f"http://localhost:{settings.frontend_port}",
    f"http://127.0.0.1:{settings.frontend_port}",
    "http://localhost:3000",    # 备选端口
    "http://localhost:80",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局异常处理 ──────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局异常处理器。
    捕获未处理的异常，返回统一格式的错误响应。
    """
    logger.error(f"未处理的异常：{exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "服务器内部错误",
            "error_type": type(exc).__name__,
        },
    )

# ── 注册路由 ──────────────────────────────────────────────────
from backend.api.auth import router as auth_router
from backend.api.voices import router as voices_router
from backend.api.conversations import router as conversations_router
from backend.api.ws import router as ws_router

app.include_router(auth_router)
app.include_router(voices_router)
app.include_router(conversations_router)
app.include_router(ws_router)

# ── 健康检查接口 ──────────────────────────────────────────────

@app.get("/api/health", tags=["系统"])
async def health_check() -> dict:
    """
    健康检查接口。
    返回 GPU 状态、模型加载情况、音色数量等信息。
    """
    import torch
    from backend.core.stt_engine import is_whisper_loaded
    from backend.core.tts_engine import get_cached_model_count

    # GPU 信息
    gpu_info: dict = {"available": False}
    try:
        if torch.cuda.is_available():
            gpu_idx = 0
            gpu_info = {
                "available": True,
                "name": torch.cuda.get_device_name(gpu_idx),
                "memory_total": round(
                    torch.cuda.get_device_properties(gpu_idx).total_memory / 1024 / 1024
                ),
                "memory_used": round(
                    (
                        torch.cuda.memory_allocated(gpu_idx)
                        + torch.cuda.memory_reserved(gpu_idx)
                    ) / 1024 / 1024
                ),
            }
    except Exception as e:
        logger.warning(f"获取 GPU 信息失败：{e}")

    # 音色数量（数据库查询）
    voice_count = 0
    try:
        from backend.database import AsyncSessionLocal
        from backend.models.voice_model import VoiceModel
        from sqlalchemy import select, func
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(func.count(VoiceModel.id)).where(VoiceModel.is_active == True)
            )
            voice_count = result.scalar() or 0
    except Exception as e:
        logger.warning(f"获取音色数量失败：{e}")

    return {
        "status": "ok",
        "gpu": gpu_info,
        "whisper_loaded": is_whisper_loaded(),
        "tts_models_loaded": get_cached_model_count(),
        "voice_count": voice_count,
    }


@app.get("/", tags=["系统"])
async def root() -> dict:
    """根路径，返回服务基本信息。"""
    return {
        "service": "Voice Chat Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
