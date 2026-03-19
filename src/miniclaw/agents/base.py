"""
MiniClaw Base Agent Class
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from miniclaw.core.state import MiniClawState
from miniclaw.utils.llm import get_llm, get_smart_llm


class BaseAgent(ABC):
    name: str = "base_agent"
    description: str = "Base agent class"
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        tools: Optional[List[BaseTool]] = None,
    ):
        self._llm = llm
        self._tools = tools or []
    
    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = get_smart_llm()
        return self._llm
    
    def get_tools(self) -> List[BaseTool]:
        return self._tools
    
    def bind_tools(self) -> Any:
        if self._tools:
            return self.llm.bind_tools(self._tools)
        return self.llm
    
    @abstractmethod
    async def process(self, state: MiniClawState) -> str:
        pass
    
    def get_last_user_message(self, state: MiniClawState) -> str:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                return msg.content
            if hasattr(msg, "content"):
                return msg.content
        return ""
    
    def update_state(self, state: MiniClawState, updates: Dict[str, Any]) -> MiniClawState:
        new_state = dict(state)
        new_state.update(updates)
        return new_state
