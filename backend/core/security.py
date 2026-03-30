"""
认证与安全核心模块
提供密码哈希、JWT 生成/验证、依赖注入等功能
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.database import get_db
from backend.utils.logger import get_logger

logger = get_logger(__name__)

settings = get_settings()

# bcrypt 密码哈希上下文
# bcrypt 自动处理 salt，是当前最安全的密码哈希方案之一
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer Token 解析器
bearer_scheme = HTTPBearer(auto_error=True)

# JWT 算法
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """
    对密码进行 bcrypt 哈希。

    Args:
        password: 明文密码

    Returns:
        str: bcrypt 哈希值
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希值是否匹配。
    使用常量时间比较，防止时序攻击。

    Args:
        plain_password: 明文密码
        hashed_password: 存储的 bcrypt 哈希值

    Returns:
        bool: 是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int, email: str) -> str:
    """
    生成 JWT Access Token。

    Payload 包含：
    - sub: 用户 ID（字符串）
    - email: 用户邮箱
    - exp: 过期时间
    - iat: 签发时间

    Args:
        user_id: 用户 ID
        email: 用户邮箱

    Returns:
        str: JWT Token 字符串
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

    Args:
        token: JWT Token 字符串

    Returns:
        dict: Payload 字典，验证失败返回 None
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

    流程：
    1. 从 Authorization Header 提取 Bearer Token
    2. 解码 JWT，获取 user_id
    3. 查询数据库，返回用户对象

    Args:
        credentials: HTTP Bearer 凭证
        db: 数据库会话

    Returns:
        User: 当前登录用户

    Raises:
        HTTPException 401: Token 无效或用户不存在
    """
    # 在函数内部导入以避免循环导入
    from backend.models.user import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 解码 Token
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

    # 查询用户
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

    Args:
        token: Query 参数中的 JWT Token

    Returns:
        dict: Payload 字典，验证失败返回 None
    """
    return decode_access_token(token)
