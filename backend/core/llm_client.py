"""
LLM 客户端模块
支持 OpenAI 兼容接口的流式对话
LLM_API_KEY 为空时自动返回 mock 回复，不崩溃
对话上下文管理：最近10轮，存 Redis
"""

import json
from typing import AsyncGenerator, Optional

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# 系统 prompt（可通过环境变量配置扩展）
DEFAULT_SYSTEM_PROMPT = (
    "你是一个友好、智能的语音助手。请用简洁清晰的语言回答用户的问题。"
    "回答要自然流畅，适合语音播放，避免使用 Markdown 格式符号。"
)

# 每个对话保留的最大轮次（1轮 = 1条用户消息 + 1条助手回复）
MAX_CONTEXT_ROUNDS = 10


# Redis 客户端（懒加载）
_redis_client = None


async def _get_redis():
    """获取 Redis 客户端（单例，失败时返回 None）。"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as redis
        client = redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis_client = client
        return _redis_client
    except Exception as e:
        logger.warning(f"LLM Redis 连接失败，上下文将不持久化：{e}")
        return None


async def get_conversation_context(conversation_id: int) -> list[dict]:
    """
    从 Redis 获取对话上下文（最近10轮消息）。

    Key 格式：llm:context:{conversation_id}
    Value：JSON 序列化的消息列表

    Args:
        conversation_id: 对话 ID

    Returns:
        list[dict]: 消息列表，格式 [{"role": "user/assistant", "content": "..."}]
    """
    redis = await _get_redis()
    if redis is None:
        return []

    try:
        key = f"llm:context:{conversation_id}"
        data = await redis.get(key)
        if data:
            return json.loads(data)
        return []
    except Exception as e:
        logger.warning(f"获取对话上下文失败（conv={conversation_id}）：{e}")
        return []


async def save_conversation_context(
    conversation_id: int,
    messages: list[dict],
) -> None:
    """
    保存对话上下文到 Redis。
    只保留最近10轮（20条消息），避免 Token 爆炸。

    Args:
        conversation_id: 对话 ID
        messages: 消息列表（不含 system prompt）
    """
    redis = await _get_redis()
    if redis is None:
        return

    try:
        # 只保留最近 MAX_CONTEXT_ROUNDS * 2 条（10轮 = 20条）
        trimmed = messages[-(MAX_CONTEXT_ROUNDS * 2):]

        key = f"llm:context:{conversation_id}"
        # 24小时过期（避免无限积累）
        await redis.setex(key, 86400, json.dumps(trimmed, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"保存对话上下文失败（conv={conversation_id}）：{e}")


async def generate_title(user_message: str, assistant_reply: str) -> Optional[str]:
    """
    根据对话第一轮内容自动生成简洁标题（8~15字）。
    LLM 未配置时降级为截取用户消息前20字。

    Args:
        user_message: 用户第一条消息
        assistant_reply: AI 第一条回复

    Returns:
        str: 生成的标题，失败返回 None
    """
    if not settings.llm_enabled:
        # 无 LLM 时用用户消息首段作为标题
        title = user_message.strip()[:20]
        return (title + "…") if len(user_message.strip()) > 20 else title or None

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "根据用户和AI的第一轮对话，生成一个简洁的对话标题（8~15字）。"
                        "要求：不含引号、不含标点、直接返回标题文字。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"用户：{user_message[:150]}\n"
                        f"AI：{assistant_reply[:150]}"
                    ),
                },
            ],
            max_tokens=40,
            temperature=0.3,
            stream=False,
        )
        raw = response.choices[0].message.content or ""
        # 去除可能包裹的引号或书名号
        title = raw.strip().strip('"\'「」《》""').strip()
        return title[:50] if title else None

    except Exception as e:
        logger.warning(f"标题生成失败：{e}")
        return None


async def clear_conversation_context(conversation_id: int) -> None:
    """
    清除指定对话的上下文缓存。

    Args:
        conversation_id: 对话 ID
    """
    redis = await _get_redis()
    if redis is None:
        return
    try:
        await redis.delete(f"llm:context:{conversation_id}")
    except Exception as e:
        logger.warning(f"清除对话上下文失败：{e}")


async def _mock_stream_response(user_input: str) -> AsyncGenerator[str, None]:
    """
    LLM 未配置时的 Mock 流式响应。
    模拟逐字输出效果。

    Args:
        user_input: 用户输入

    Yields:
        str: 模拟的回复片段
    """
    mock_reply = (
        f"[LLM 未配置，这是测试回复] 你说的是：{user_input[:50]}。"
        "请在 .env 文件中配置 LLM_API_KEY 以启用真实对话。"
    )
    # 按字符逐个 yield，模拟流式效果
    for char in mock_reply:
        yield char


async def stream_chat(
    user_message: str,
    conversation_id: int,
    system_prompt: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    流式对话接口，逐 token 生成 AI 回复。

    流程：
    1. 从 Redis 加载历史上下文
    2. 追加用户消息
    3. 调用 LLM（或 Mock）流式生成回复
    4. 收集完整回复后保存上下文

    Args:
        user_message: 用户输入文字
        conversation_id: 对话 ID（用于上下文管理）
        system_prompt: 自定义系统 prompt（None 使用默认）

    Yields:
        str: LLM 回复文字片段（流式）
    """
    # LLM 未配置，使用 Mock
    if not settings.llm_enabled:
        logger.info("LLM 未配置（API Key 为空），使用 mock 回复")
        async for chunk in _mock_stream_response(user_message):
            yield chunk
        return

    # 加载历史上下文
    context_messages = await get_conversation_context(conversation_id)

    # 构建完整消息列表
    sys_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": sys_prompt},
        *context_messages,
        {"role": "user", "content": user_message},
    ]

    # 收集完整回复（用于保存上下文）
    full_reply = []

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

        logger.debug(f"LLM 请求：model={settings.llm_model}，上下文={len(context_messages)}条")

        # 流式请求
        stream = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=1000,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                full_reply.append(delta.content)
                yield delta.content

    except Exception as e:
        error_msg = f"[LLM 请求失败：{type(e).__name__}] 请检查 API 配置"
        logger.error(f"LLM 流式请求失败：{e}")
        yield error_msg
        full_reply.append(error_msg)

    finally:
        # 无论成功失败，都保存上下文（保留对话连续性）
        if full_reply:
            assistant_reply = "".join(full_reply)
            new_context = [
                *context_messages,
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_reply},
            ]
            await save_conversation_context(conversation_id, new_context)
            logger.debug(f"对话上下文已保存：conv={conversation_id}，共{len(new_context)}条")
