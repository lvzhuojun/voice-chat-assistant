"""
用户认证 API 路由
提供注册、登录、获取当前用户接口
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.limiter import limiter

from backend.database import get_db
from backend.models.user import User
from backend.schemas.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
)
from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def register(
    request: Request,
    body: UserRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    用户注册接口。

    - 检查邮箱是否已被注册
    - 密码 bcrypt 哈希存储
    - 注册成功后自动颁发 JWT Token

    Args:
        request: 注册请求（email、password、username）
        db: 数据库会话

    Returns:
        TokenResponse: JWT Token + 用户信息
    """
    # 检查邮箱是否已注册
    result = await db.execute(select(User).where(User.email == body.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册",
        )

    # 创建用户
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        username=body.username,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"新用户注册：{user.email} (id={user.id})")

    # 生成 JWT Token
    token = create_access_token(user_id=user.id, email=user.email)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: UserLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    用户登录接口。

    - 验证邮箱和密码
    - 登录成功后颁发 JWT Token

    Args:
        request: 登录请求（email、password）
        db: 数据库会话

    Returns:
        TokenResponse: JWT Token + 用户信息
    """
    # 查找用户
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # 验证用户存在且密码正确（使用常量时间比较防止时序攻击）
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )

    logger.info(f"用户登录：{user.email} (id={user.id})")

    # 生成 JWT Token
    token = create_access_token(user_id=user.id, email=user.email)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """
    获取当前登录用户信息。
    需要 Authorization: Bearer {token} Header。

    Args:
        current_user: 通过 JWT 验证的当前用户（依赖注入）

    Returns:
        UserResponse: 用户信息
    """
    return UserResponse.model_validate(current_user)
