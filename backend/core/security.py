"""
认证与安全核心模块
提供密码哈希、JWT 生成/验证、依赖注入等功能
Core authentication and security module.
Provides password hashing, JWT creation/verification, and FastAPI dependency injection.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.database import get_db
from backend.utils.logger import get_logger

logger = get_logger(__name__)

settings = get_settings()

# Bearer Token 解析器 / HTTP Bearer token extractor
bearer_scheme = HTTPBearer(auto_error=True)

# JWT 算法 / JWT signing algorithm
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: int, email: str) -> str:
    """
    生成 JWT Access Token。
    Generate a JWT access token.

    Payload 包含：
    - sub: 用户 ID（字符串）
    - email: 用户邮箱
    - exp: 过期时间
    - iat: 签发时间

    Payload fields:
    - sub: user ID (as string)
    - email: user email address
    - exp: expiration timestamp
    - iat: issued-at timestamp

    Args:
        user_id: 用户 ID / User identifier
        email: 用户邮箱 / User email address

    Returns:
        str: JWT Token 字符串 / Encoded JWT token string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_expire_days)

    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": expire,
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码并验证 JWT Token。
    Decode and verify a JWT access token.

    Args:
        token: JWT Token 字符串 / Encoded JWT token string

    Returns:
        dict: Payload 字典，验证失败返回 None
              / Decoded payload dict, or None if verification fails
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT 验证失败：{e}")
        return None


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    FastAPI 依赖注入：从 JWT Token 获取当前用户。
    FastAPI dependency: resolve the currently authenticated user from a JWT token.

    流程：
    1. 从 Authorization Header 提取 Bearer Token
    2. 解码 JWT，获取 user_id
    3. 查询数据库，返回用户对象

    Flow:
    1. Extract the Bearer token from the Authorization header
    2. Decode the JWT to retrieve the user_id
    3. Query the database and return the user object

    Args:
        credentials: HTTP Bearer 凭证 / HTTP Bearer credentials from the request
        db: 数据库会话 / Async database session

    Returns:
        User: 当前登录用户 / The currently authenticated User ORM instance

    Raises:
        HTTPException 401: Token 无效或用户不存在 / If the token is invalid or the user does not exist
    """
    # 在函数内部导入以避免循环导入 / Import here to avoid circular import issues
    from backend.models.user import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 解码 Token / Decode and validate the JWT token
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise credentials_exception

    user_id_str: Optional[str] = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    # 查询用户 / Fetch the user record from the database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    return user


def get_token_from_query(token: str) -> Optional[dict]:
    """
    从 Query 参数中验证 Token（用于 WebSocket 连接）。
    WebSocket 无法使用 Authorization Header，改用 ?token= 参数。
    Validate a token supplied as a query parameter (used for WebSocket connections).
    WebSocket connections cannot send an Authorization header, so ?token= is used instead.

    Args:
        token: Query 参数中的 JWT Token / JWT token passed as a query parameter

    Returns:
        dict: Payload 字典，验证失败返回 None
              / Decoded payload dict, or None if verification fails
    """
    return decode_access_token(token)
