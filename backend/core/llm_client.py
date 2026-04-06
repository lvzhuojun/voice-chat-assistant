"""
LLM 客户端模块
LLM client module.
支持 OpenAI 兼容接口的流式对话
Supports streaming conversation via OpenAI-compatible API.
LLM_API_KEY 为空时自动返回 mock 回复，不崩溃
Automatically returns a mock reply when LLM_API_KEY is empty, without crashing.
对话上下文管理：最近10轮，存 Redis
Conversation context management: last 10 rounds, stored in Redis.
"""

import json
from typing import AsyncGenerator, Optional

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# 系统 prompt（可通过环境变量配置扩展）
# System prompt (can be extended via environment variable configuration)
DEFAULT_SYSTEM_PROMPT = (
    "你是一个友好、智能的语音助手。请用简洁清晰的语言回答用户的问题。"
    "回答要自然流畅，适合语音播放，避免使用 Markdown 格式符号。"
)

# 每个对话保留的最大轮次（1轮 = 1条用户消息 + 1条助手回复）
# Maximum number of rounds to retain per conversation (1 round = 1 user message + 1 assistant reply)
MAX_CONTEXT_ROUNDS = 10

# LLM 错误标记（特殊前缀，pipeline 检测到后终止 TTS，避免合成错误文字）
# LLM error marker (special prefix; when detected by the pipeline, TTS is terminated
# to avoid synthesizing error text)
LLM_ERROR_MARKER = "\x00LLM_ERR\x00"


# Redis 客户端（懒加载）/ Redis client (lazy initialization)
_redis_client = None


async def _get_redis():
    """获取 Redis 客户端（单例，失败时返回 None）。
    Retrieve the Redis client (singleton; returns None on failure)."""
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
    Retrieve conversation context from Redis (last 10 rounds of messages).

    Key 格式：llm:context:{conversation_id}
    Key format: llm:context:{conversation_id}
    Value：JSON 序列化的消息列表
    Value: JSON-serialized message list

    Args:
        conversation_id: 对话 ID / Conversation ID

    Returns:
        list[dict]: 消息列表，格式 [{"role": "user/assistant", "content": "..."}]
        / Message list in the format [{"role": "user/assistant", "content": "..."}]
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
    Save conversation context to Redis.
    只保留最近10轮（20条消息），避免 Token 爆炸。
    Retains only the most recent 10 rounds (20 messages) to prevent token explosion.

    Args:
        conversation_id: 对话 ID / Conversation ID
        messages: 消息列表（不含 system prompt）/ Message list (excluding the system prompt)
    """
    redis = await _get_redis()
    if redis is None:
        return

    try:
        # 只保留最近 MAX_CONTEXT_ROUNDS * 2 条（10轮 = 20条）
        # Retain only the last MAX_CONTEXT_ROUNDS * 2 messages (10 rounds = 20 messages)
        trimmed = messages[-(MAX_CONTEXT_ROUNDS * 2):]

        key = f"llm:context:{conversation_id}"
        # 24小时过期（避免无限积累）/ Expire after 24 hours (prevents unbounded accumulation)
        await redis.setex(key, 86400, json.dumps(trimmed, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"保存对话上下文失败（conv={conversation_id}）：{e}")


async def generate_title(user_message: str, assistant_reply: str) -> Optional[str]:
    """
    根据对话第一轮内容自动生成简洁标题（8~15字）。
    Automatically generate a concise title (8~15 characters) from the first round of conversation.
    LLM 未配置时降级为截取用户消息前20字。
    Falls back to truncating the first 20 characters of the user message when LLM is not configured.

    Args:
        user_message: 用户第一条消息 / User's first message
        assistant_reply: AI 第一条回复 / AI's first reply

    Returns:
        str: 生成的标题，失败返回 None / Generated title; None on failure
    """
    if not settings.llm_enabled:
        # 无 LLM 时用用户消息首段作为标题
        # Use the first segment of the user message as the title when LLM is unavailable
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
        # Strip any surrounding quotation marks or title marks
        title = raw.strip().strip('"\'「」《》""').strip()
        return title[:50] if title else None

    except Exception as e:
        logger.warning(f"标题生成失败：{e}")
        return None


async def clear_conversation_context(conversation_id: int) -> None:
    """
    清除指定对话的上下文缓存。
    Clear the context cache for the specified conversation.

    Args:
        conversation_id: 对话 ID / Conversation ID
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
    Mock streaming response used when LLM is not configured.
    模拟逐字输出效果。
    Simulates character-by-character output.

    Args:
        user_input: 用户输入 / User input

    Yields:
        str: 模拟的回复片段 / Simulated reply fragment
    """
    mock_reply = (
        f"[LLM 未配置，这是测试回复] 你说的是：{user_input[:50]}。"
        "请在 .env 文件中配置 LLM_API_KEY 以启用真实对话。"
    )
    # 按字符逐个 yield，模拟流式效果
    # Yield one character at a time to simulate streaming
    for char in mock_reply:
        yield char


async def stream_chat(
    user_message: str,
    conversation_id: int,
    system_prompt: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    流式对话接口，逐 token 生成 AI 回复。
    Streaming chat interface that generates AI replies token by token.

    流程：
    Workflow:
    1. 从 Redis 加载历史上下文 / Load historical context from Redis
    2. 追加用户消息 / Append the user message
    3. 调用 LLM（或 Mock）流式生成回复 / Call LLM (or Mock) for streaming reply generation
    4. 收集完整回复后保存上下文 / Save context after collecting the full reply

    Args:
        user_message: 用户输入文字 / User input text
        conversation_id: 对话 ID（用于上下文管理）/ Conversation ID (used for context management)
        system_prompt: 自定义系统 prompt（None 使用默认）
                       / Custom system prompt (None uses the default)

    Yields:
        str: LLM 回复文字片段（流式）/ LLM reply text fragment (streaming)
    """
    # LLM 未配置，使用 Mock / LLM not configured, use Mock
    if not settings.llm_enabled:
        logger.info("LLM 未配置（API Key 为空），使用 mock 回复")
        async for chunk in _mock_stream_response(user_message):
            yield chunk
        return

    # 加载历史上下文 / Load historical context
    context_messages = await get_conversation_context(conversation_id)

    # 构建完整消息列表 / Build the full message list
    sys_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": sys_prompt},
        *context_messages,
        {"role": "user", "content": user_message},
    ]

    # 收集完整回复（用于保存上下文）/ Collect the full reply (for saving context)
    full_reply = []

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

        logger.debug(f"LLM 请求：model={settings.llm_model}，上下文={len(context_messages)}条")

        # 流式请求 / Streaming request
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
        error_msg = f"LLM 请求失败（{type(e).__name__}），请检查 API 配置"
        logger.error(f"LLM 流式请求失败：{e}", exc_info=True)
        # 使用特殊标记前缀，让 pipeline 识别后终止 TTS，不将错误存入上下文
        # Use the special marker prefix so the pipeline can detect it, terminate TTS,
        # and avoid storing the error in the context
        yield LLM_ERROR_MARKER + error_msg
        return  # full_reply 为空，finally 不会保存错误到上下文
               # full_reply is empty, so finally will not save the error to context

    finally:
        # 仅在有实际回复内容时保存上下文（错误时 full_reply 为空，跳过）
        # Save context only when there is actual reply content
        # (full_reply is empty on error, so this is skipped)
        if full_reply:
            assistant_reply = "".join(full_reply)
            new_context = [
                *context_messages,
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_reply},
            ]
            await save_conversation_context(conversation_id, new_context)
            logger.debug(f"对话上下文已保存：conv={conversation_id}，共{len(new_context)}条")
