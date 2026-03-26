"""
MiniClaw 异常处理模块
定义所有自定义异常类和错误处理工具
"""

from typing import Optional, Dict, Any
from enum import Enum


class MiniClawErrorCode(str, Enum):
    """MiniClaw 错误码"""
    # 系统错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    
    # Agent 错误
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AGENT_EXECUTION_ERROR = "AGENT_EXECUTION_ERROR"
    SUPERVISOR_ROUTING_ERROR = "SUPERVISOR_ROUTING_ERROR"
    
    # 工具错误
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    
    # MCP 错误
    MCP_CONNECTION_ERROR = "MCP_CONNECTION_ERROR"
    MCP_PROTOCOL_ERROR = "MCP_PROTOCOL_ERROR"
    MCP_TOOL_ERROR = "MCP_TOOL_ERROR"
    
    # LLM 错误
    LLM_ERROR = "LLM_ERROR"
    LLM_RATE_LIMIT = "LLM_RATE_LIMIT"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    
    # 状态错误
    STATE_ERROR = "STATE_ERROR"
    CHECKPOINT_ERROR = "CHECKPOINT_ERROR"


class MiniClawException(Exception):
    """MiniClaw 基础异常类"""
    
    def __init__(
        self,
        message: str,
        code: MiniClawErrorCode = MiniClawErrorCode.INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.original_error = original_error
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": True,
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }
    
    def __str__(self) -> str:
        if self.original_error:
            return f"[{self.code.value}] {self.message} (原始错误: {self.original_error})"
        return f"[{self.code.value}] {self.message}"


class AgentException(MiniClawException):
    """Agent 相关异常"""
    
    def __init__(
        self,
        message: str,
        code: MiniClawErrorCode = MiniClawErrorCode.AGENT_EXECUTION_ERROR,
        agent_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if agent_name:
            details["agent_name"] = agent_name
        super().__init__(message, code, details, **kwargs)


class ToolException(MiniClawException):
    """工具执行异常"""
    
    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        code: MiniClawErrorCode = MiniClawErrorCode.TOOL_EXECUTION_ERROR,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if tool_name:
            details["tool_name"] = tool_name
        super().__init__(message, code, details, **kwargs)


class LLMException(MiniClawException):
    """LLM 调用异常"""
    
    def __init__(
        self,
        message: str,
        code: MiniClawErrorCode = MiniClawErrorCode.LLM_ERROR,
        **kwargs
    ):
        super().__init__(message, code, **kwargs)


class StateException(MiniClawException):
    """状态管理异常"""
    
    def __init__(
        self,
        message: str,
        code: MiniClawErrorCode = MiniClawErrorCode.STATE_ERROR,
        **kwargs
    ):
        super().__init__(message, code, **kwargs)


class RetryableError(MiniClawException):
    """可重试的错误"""
    pass


class NonRetryableError(MiniClawException):
    """不可重试的错误"""
    pass
