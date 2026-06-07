"""
API Key Rotation — API Key 自动轮换

对标 OpenClaw 的 Auth Profile Rotation：
  当 API 调用遇到速率限制 (429) 时，自动切换到下一个 API Key，
  避免单 Key 被限流导致服务不可用。

核心逻辑：
  1. 遍历去重后的 API Key 列表
  2. 成功 → 返回结果
  3. 速率限制 (429 / rate_limit) → 轮换到下一个 Key
  4. 瞬态错误 (timeout / 5xx) → 同一 Key 重试（最多 2 次）
  5. 其他错误 → 直接抛出
"""

from typing import Any, Callable, Coroutine, List, Optional

from loguru import logger


# 同一 Key 遇到瞬态错误时的最大重试次数
_MAX_TRANSIENT_RETRIES = 2


def is_api_key_rate_limit_error(error: Exception) -> bool:
    """
    检测是否为速率限制错误

    对标 OpenClaw 的 isRateLimitError：
    - HTTP 429
    - 错误消息包含 rate_limit / rate limit / too many requests
    """
    error_str = str(error).lower()
    if "429" in error_str:
        return True
    if "rate_limit" in error_str or "rate limit" in error_str:
        return True
    if "too many requests" in error_str:
        return True

    # 检查异常的 status_code 属性
    status_code = getattr(error, "status_code", None)
    if status_code == 429:
        return True

    # 检查 response 属性
    response = getattr(error, "response", None)
    if response is not None:
        resp_status = getattr(response, "status_code", None)
        if resp_status == 429:
            return True

    return False


def should_retry_same_key(error: Exception) -> bool:
    """
    检测是否为瞬态错误（应重试同一 Key）

    对标 OpenClaw 的 isTransientError：
    - timeout
    - 5xx 服务端错误
    - connection error
    """
    error_str = str(error).lower()
    if "timeout" in error_str:
        return True
    if "connection" in error_str:
        return True

    # 检查 5xx 状态码
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int) and 500 <= status_code < 600:
        return True

    response = getattr(error, "response", None)
    if response is not None:
        resp_status = getattr(response, "status_code", None)
        if isinstance(resp_status, int) and 500 <= resp_status < 600:
            return True

    return False


def collect_provider_api_keys() -> List[str]:
    """
    收集主 Key + 额外 Keys

    对标 OpenClaw 的 collectAuthProfiles：
    从 settings 中收集主 API Key 和额外 API Keys，
    去重后返回。
    """
    from config.settings import settings

    keys: List[str] = []

    # 主 Key
    main_key = settings.effective_api_key
    if main_key:
        keys.append(main_key)

    # 额外 Keys
    extra_keys_str = getattr(settings, "LLM_EXTRA_API_KEYS", "")
    if extra_keys_str:
        for key in extra_keys_str.split(","):
            key = key.strip()
            if key and key not in keys:
                keys.append(key)

    return keys


async def execute_with_api_key_rotation(
    exec_fn: Callable[[str], Coroutine],
    api_keys: List[str],
    **kwargs,
) -> Any:
    """
    带 API Key 轮换的执行函数

    对标 OpenClaw 的 executeWithAuthProfileRotation：
    遍历 API Key 列表，遇到速率限制自动切换 Key，
    遇到瞬态错误重试同一 Key。

    Args:
        exec_fn: 接收 api_key 参数的异步执行函数
        api_keys: 去重后的 API Key 列表

    Returns:
        exec_fn 的返回值

    Raises:
        最后一个 Key 的错误（如果所有 Key 都失败）
    """
    # 去重，保持顺序
    seen: set[str] = set()
    unique_keys: List[str] = []
    for key in api_keys:
        if key not in seen:
            seen.add(key)
            unique_keys.append(key)

    if not unique_keys:
        # 没有 Key，直接执行（可能不需要 Key 的 provider）
        return await exec_fn("")

    last_error: Optional[Exception] = None

    for key_index, api_key in enumerate(unique_keys):
        key_label = f"key[{key_index}]({api_key[:8]}...)" if len(api_key) > 8 else f"key[{key_index}]"

        # 瞬态错误重试
        for retry in range(_MAX_TRANSIENT_RETRIES + 1):
            try:
                result = await exec_fn(api_key)
                if key_index > 0:
                    logger.info(f"API key rotation succeeded with {key_label}")
                return result
            except Exception as e:
                last_error = e

                if is_api_key_rate_limit_error(e):
                    logger.warning(
                        f"Rate limit hit with {key_label}, rotating to next key "
                        f"(retry={retry}, remaining_keys={len(unique_keys) - key_index - 1})"
                    )
                    break  # 切换到下一个 Key

                if should_retry_same_key(e):
                    if retry < _MAX_TRANSIENT_RETRIES:
                        logger.warning(
                            f"Transient error with {key_label}, retrying same key "
                            f"(retry={retry + 1}/{_MAX_TRANSIENT_RETRIES}): {e}"
                        )
                        continue
                    else:
                        logger.warning(
                            f"Transient error with {key_label} exhausted retries, "
                            f"rotating to next key"
                        )
                        break  # 重试耗尽，切换 Key

                # 非速率限制、非瞬态错误 → 直接抛出
                raise

    # 所有 Key 都失败
    logger.error(f"All API keys exhausted, last error: {last_error}")
    if last_error is not None:
        raise last_error
    raise RuntimeError("All API keys exhausted with no specific error")
