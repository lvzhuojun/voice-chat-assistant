"""
数据库连接模块
使用 SQLAlchemy 2.0 异步引擎 + Session 工厂
Database connection module.
Uses SQLAlchemy 2.0 async engine with an async session factory.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

settings = get_settings()

# 将 postgresql:// 转换为 postgresql+asyncpg://（异步驱动）
# Convert postgresql:// to postgresql+asyncpg:// for the async driver
_db_url = settings.database_url
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# 创建异步引擎
# Create the async engine
# pool_pre_ping=True：连接池在使用前先 ping，防止"连接已断开"错误
# pool_pre_ping=True: ping the connection before use to prevent "connection lost" errors
engine = create_async_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,  # 生产环境设为 False，调试时可改为 True / Set False in production, True for debugging
)

# Session 工厂 / Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 提交后不自动过期，避免 lazy load 问题 / Prevents lazy-load issues after commit
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """
    所有 ORM 模型的基类。
    继承 DeclarativeBase（SQLAlchemy 2.0 风格）。
    Base class for all ORM models.
    Inherits from DeclarativeBase (SQLAlchemy 2.0 style).
    """
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入：提供数据库 Session。
    使用 async with 确保 Session 正确关闭。
    FastAPI dependency injection: provides a database session.
    Uses async with to ensure the session is properly closed.

    Yields:
        AsyncSession: 数据库会话 / Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_all_tables() -> None:
    """
    创建所有数据库表（仅用于开发/测试，生产使用 Alembic）。
    Create all database tables (development/testing only; use Alembic in production).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
