"""
Alembic 环境配置
支持异步引擎（asyncpg），从 .env 读取数据库 URL
Alembic environment configuration.
Supports async engine (asyncpg) and reads the database URL from .env.
"""

import asyncio
from logging.config import fileConfig
from pathlib import Path
import sys
import os

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 将项目根目录加入 sys.path，确保可以导入 backend 模块
# backend/alembic/env.py -> 上两级是项目根
# Insert the project root into sys.path so that backend modules can be imported.
# backend/alembic/env.py is two levels below the project root.
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 加载 .env 文件 / Load environment variables from the .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# 导入应用配置和模型元数据 / Import application settings and ORM metadata
from backend.config import get_settings
from backend.database import Base

# 导入所有模型，确保 metadata 中有表信息
# Import all ORM models to ensure their tables are registered in Base.metadata
from backend.models import User, VoiceModel, Conversation, Message  # noqa: F401

# Alembic Config 对象 / Alembic Config object provided by the migration context
config = context.config

# 从 .env 覆盖数据库 URL（转为异步驱动）
# Override the database URL from settings, converting to the asyncpg driver scheme
settings = get_settings()
db_url = settings.database_url
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
config.set_main_option("sqlalchemy.url", db_url)

# 配置 Python 日志 / Configure Python standard logging from the Alembic ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 自动迁移的目标元数据 / Target metadata for autogenerate migration comparison
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    离线模式：生成 SQL 脚本而不连接数据库。
    用于 alembic upgrade --sql 命令。
    Offline mode: generate SQL scripts without establishing a database connection.
    Used with the `alembic upgrade --sql` command.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    在同步连接中执行迁移。
    Execute migrations within a synchronous database connection.
    """
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    异步模式：连接数据库并执行迁移。
    Async mode: establish a database connection and run migrations asynchronously.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    在线模式（默认）：连接数据库执行迁移。
    Online mode (default): connect to the database and execute migrations.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
