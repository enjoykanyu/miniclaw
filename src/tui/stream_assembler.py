"""
StreamAssembler — 流式响应组装器

对标 OpenClaw 的 TuiStreamAssembler (tui-stream-assembler.ts)：
  - 增量 delta 组装
  - thinking/content 分离
  - 边界文本处理
  - 最终文本比较与回退
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class StreamChunk:
    """流式块"""
    content: str = ""
    thinking: str = ""
    is_final: bool = False
    error: Optional[str] = None


class StreamAssembler:
    """
    对标 OpenClaw 的 TuiStreamAssembler

    将增量 delta 消息组装为完整的显示文本。
    处理 thinking 和 content 的分离，以及边界文本丢失问题。
    """

    def __init__(self, show_thinking: bool = False):
        self.show_thinking = show_thinking
        self._content_buffer: str = ""
        self._thinking_buffer: str = ""
        self._run_buffers: Dict[str, str] = {}

    def ingest_delta(self, event: dict) -> Optional[StreamChunk]:
        """
        对标 OpenClaw 的 ingestDelta

        从 LangGraph astream_events 事件中提取内容，
        返回更新后的显示文本块。
        """
        event_name = event.get("event", "")
        data = event.get("data", {})

        chunk = StreamChunk()

        # 处理 on_chat_model_stream 事件（LLM token 流）
        if event_name == "on_chat_model_stream":
            msg = data.get("chunk")
            if msg is None:
                return None

            # 提取 content
            content = getattr(msg, "content", None)
            if content:
                chunk.content = content if isinstance(content, str) else str(content)
                self._content_buffer += chunk.content

            # 提取 thinking（如果模型支持）
            # OpenAI 兼容模型的 thinking/reasoning 内容
            additional_kwargs = getattr(msg, "additional_kwargs", {})
            thinking = additional_kwargs.get("thinking") or additional_kwargs.get("reasoning")
            if thinking:
                chunk.thinking = thinking if isinstance(thinking, str) else str(thinking)
                self._thinking_buffer += chunk.thinking

            return chunk if (chunk.content or chunk.thinking) else None

        # 处理 on_chain_end 事件（最终结果）
        if event_name == "on_chain_end":
            output = data.get("output", {})
            if isinstance(output, dict):
                messages = output.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    content = getattr(last_msg, "content", "")
                    if content and isinstance(content, str):
                        chunk.content = content
                        chunk.is_final = True
                        return chunk

        return None

    def finalize(self, error_message: Optional[str] = None) -> StreamChunk:
        """
        对标 OpenClaw 的 finalize

        处理最终消息，比较流式文本和最终文本。
        """
        chunk = StreamChunk(is_final=True)

        if error_message:
            chunk.error = error_message
            return chunk

        chunk.content = self._content_buffer
        chunk.thinking = self._thinking_buffer

        return chunk

    def reset(self) -> None:
        """重置缓冲区"""
        self._content_buffer = ""
        self._thinking_buffer = ""
        self._run_buffers.clear()

    @property
    def current_content(self) -> str:
        return self._content_buffer

    @property
    def current_thinking(self) -> str:
        return self._thinking_buffer
