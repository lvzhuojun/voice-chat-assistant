"""
日志工具模块
使用 loguru 提供结构化日志，支持按模块区分颜色
"""

import sys
from loguru import logger

# 移除默认处理器
logger.remove()

# 控制台输出（带颜色和格式）
logger.add(
    sys.stderr,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
    level="INFO",
    colorize=True,
)

# 文件输出（循环写入，保留 7 天）
logger.add(
    "logs/app.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    level="DEBUG",
    rotation="00:00",      # 每天零点切换文件
    retention="7 days",    # 保留 7 天
    compression="zip",     # 旧文件压缩
    encoding="utf-8",
)

# 错误单独文件
logger.add(
    "logs/error.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    level="ERROR",
    rotation="1 week",
    retention="30 days",
    compression="zip",
    encoding="utf-8",
)


def get_logger(name: str):
    """
    获取带模块名的子 logger。

    Args:
        name: 模块名称（通常用 __name__）

    Returns:
        loguru.Logger: 子 logger 实例
    """
    return logger.bind(name=name)
