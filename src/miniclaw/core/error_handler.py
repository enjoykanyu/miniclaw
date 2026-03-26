"""
MiniClaw 错误处理和重试机制
提供统一的错误处理、重试、降级策略
"""

import logging
import functools
from typing import Callable, Any, Optional, TypeVar, Union, List
from tenacity import (
    retry as tenacity_retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryCallState,
)

from miniclaw.core.exceptions import (
    MiniClawException,
    RetryableError,
    NonRetryableError,
    MiniClawErrorCode,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def is_retryable_error(exception: Exception) -> bool:
    """判断错误是否可重试"""
    # 不可重试的错误类型
    non_retryable_codes = {
        MiniClawErrorCode.CONFIG_ERROR,
        MiniClawErrorCode.AGENT_NOT_FOUND,
        MiniClawErrorCode.TOOL_NOT_FOUND,
        MiniClawErrorCode.STATE_ERROR,
    }
    
    if isinstance(exception, NonRetryableError):
        return False
    
    if isinstance(exception, MiniClawException):
        return exception.code not in non_retryable_codes
    
    # 网络相关错误通常可重试
    retryable_exceptions = (
        ConnectionError,
        TimeoutError,
        RetryableError,
    )
    
    return isinstance(exception, retryable_exceptions)


def retry_with_fallback(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    fallback_value: Optional[T] = None,
    on_retry: Optional[Callable[[RetryCallState], None]] = None,
):
    """
    重试装饰器，支持降级处理
    
    Args:
        max_attempts: 最大重试次数
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）
        fallback_value: 失败时的降级值
        on_retry: 重试时的回调函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                # 使用 tenacity 进行重试
                retrying_func = tenacity_retry(
                    stop=stop_after_attempt(max_attempts),
                    wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                    retry=retry_if_exception_type((RetryableError, ConnectionError, TimeoutError)),
                    before_sleep=before_sleep_log(logger, logging.WARNING),
                    reraise=True,
                )(func)
                
                return await retrying_func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Function {func.__name__} failed after {max_attempts} attempts: {e}")
                
                if fallback_value is not None:
                    logger.info(f"Using fallback value for {func.__name__}")
                    return fallback_value
                
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                retrying_func = tenacity_retry(
                    stop=stop_after_attempt(max_attempts),
                    wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                    retry=retry_if_exception_type((RetryableError, ConnectionError, TimeoutError)),
                    before_sleep=before_sleep_log(logger, logging.WARNING),
                    reraise=True,
                )(func)
                
                return retrying_func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Function {func.__name__} failed after {max_attempts} attempts: {e}")
                
                if fallback_value is not None:
                    logger.info(f"Using fallback value for {func.__name__}")
                    return fallback_value
                
                raise
        
        # 根据函数类型返回对应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class ErrorHandler:
    """错误处理器，提供统一的错误处理逻辑"""
    
    def __init__(self):
        self._error_callbacks: List[Callable[[MiniClawException], None]] = []
        self._fallback_responses: dict = {}
    
    def register_error_callback(self, callback: Callable[[MiniClawException], None]):
        """注册错误回调函数"""
        self._error_callbacks.append(callback)
    
    def set_fallback_response(self, error_code: MiniClawErrorCode, response: str):
        """设置特定错误码的降级响应"""
        self._fallback_responses[error_code] = response
    
    def handle_error(self, error: Exception, context: Optional[dict] = None) -> MiniClawException:
        """
        处理错误，转换为 MiniClawException
        
        Args:
            error: 原始错误
            context: 错误上下文信息
        
        Returns:
            MiniClawException
        """
        if isinstance(error, MiniClawException):
            mini_claw_error = error
        else:
            # 包装为 MiniClawException
            mini_claw_error = MiniClawException(
                message=str(error),
                code=MiniClawErrorCode.INTERNAL_ERROR,
                details=context or {},
                original_error=error,
            )
        
        # 记录错误日志
        logger.error(
            f"Error occurred: {mini_claw_error.code.value} - {mini_claw_error.message}",
            extra={
                "error_code": mini_claw_error.code.value,
                "details": mini_claw_error.details,
                "original_error": str(mini_claw_error.original_error) if mini_claw_error.original_error else None,
            }
        )
        
        # 调用注册的回调
        for callback in self._error_callbacks:
            try:
                callback(mini_claw_error)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")
        
        return mini_claw_error
    
    def get_fallback_response(self, error: MiniClawException) -> str:
        """获取降级响应"""
        # 首先检查特定错误码的降级响应
        if error.code in self._fallback_responses:
            return self._fallback_responses[error.code]
        
        # 默认降级响应
        fallback_messages = {
            MiniClawErrorCode.LLM_RATE_LIMIT: "请求过于频繁，请稍后再试。",
            MiniClawErrorCode.LLM_TIMEOUT: "响应超时，请稍后重试。",
            MiniClawErrorCode.TOOL_TIMEOUT: "工具执行超时，请稍后重试。",
            MiniClawErrorCode.MCP_CONNECTION_ERROR: "外部服务连接失败，请检查配置。",
            MiniClawErrorCode.AGENT_NOT_FOUND: "未找到对应的智能体。",
            MiniClawErrorCode.TOOL_NOT_FOUND: "未找到对应的工具。",
        }
        
        return fallback_messages.get(
            error.code,
            "抱歉，处理您的请求时出现了错误，请稍后重试。"
        )


# 全局错误处理器实例
error_handler = ErrorHandler()


def safe_execute(
    fallback_value: Any = None,
    error_message: str = "执行失败",
    error_code: MiniClawErrorCode = MiniClawErrorCode.INTERNAL_ERROR,
):
    """
    安全执行装饰器，捕获所有异常并返回降级值
    
    Args:
        fallback_value: 失败时的返回值
        error_message: 错误消息
        error_code: 错误码
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{error_message}: {e}")
                
                # 处理错误
                if not isinstance(e, MiniClawException):
                    e = MiniClawException(
                        message=f"{error_message}: {str(e)}",
                        code=error_code,
                        original_error=e,
                    )
                
                error_handler.handle_error(e)
                
                return fallback_value
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{error_message}: {e}")
                
                if not isinstance(e, MiniClawException):
                    e = MiniClawException(
                        message=f"{error_message}: {str(e)}",
                        code=error_code,
                        original_error=e,
                    )
                
                error_handler.handle_error(e)
                
                return fallback_value
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
