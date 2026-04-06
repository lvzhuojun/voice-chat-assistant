"""
接口限流模块
使用 slowapi 实现基于 IP 的请求频率限制，防止暴力破解和接口滥用。
Rate-limiting module.
Uses slowapi to enforce per-IP request rate limits, guarding against brute-force attacks
and API abuse.

限流策略：
  - 登录接口：每 IP 每分钟 10 次
  - 注册接口：每 IP 每小时 5 次
  - 音色上传：每 IP 每小时 20 次

Rate-limit policy:
  - Login endpoint:        10 requests per IP per minute
  - Registration endpoint:  5 requests per IP per hour
  - Voice upload endpoint: 20 requests per IP per hour
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# 全局限流器实例，以客户端 IP 为 key
# 通过 X-Forwarded-For / X-Real-IP（Nginx 透传）自动识别真实 IP
# Global rate-limiter instance keyed by client IP address.
# Automatically resolves the real IP from X-Forwarded-For / X-Real-IP headers (Nginx proxy).
limiter = Limiter(key_func=get_remote_address)
