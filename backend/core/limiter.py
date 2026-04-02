"""
接口限流模块
使用 slowapi 实现基于 IP 的请求频率限制，防止暴力破解和接口滥用。

限流策略：
  - 登录接口：每 IP 每分钟 10 次
  - 注册接口：每 IP 每小时 5 次
  - 音色上传：每 IP 每小时 20 次
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# 全局限流器实例，以客户端 IP 为 key
# 通过 X-Forwarded-For / X-Real-IP（Nginx 透传）自动识别真实 IP
limiter = Limiter(key_func=get_remote_address)
