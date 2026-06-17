"""
Gateway OpenAI Compatible Interface — /v1/chat/completions

对标 OpenClaw 的 OpenAI 兼容接口：
  - 支持 streaming (SSE) 和 non-streaming 两种模式
  - Run ID 格式: chatcmpl_{uuid}
  - Non-streaming: 返回 chat.completion 对象
  - Streaming: 返回 SSE chat.completion.chunk 对象
  - build_agent_prompt() 将 OpenAI messages 格式转为内部 HumanMessage/AIMessage
  - 支持 tool/function calling 从 OpenAI 格式转换

映射关系：
  OpenClaw /v1/chat/completions → openai_chat_completions()
  OpenClaw buildAgentPrompt()   → build_agent_prompt()
"""

import json
import time
import uuid
from typing import Optional

from fastapi import Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from loguru import logger
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from agent_loop.app import get_loop_app


# ──────────────────────────────────────────────────────────
# 请求/响应模型
# ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """OpenAI 格式的消息"""
    role: str
    content: str | None = None
    name: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class ToolFunction(BaseModel):
    """OpenAI 格式的工具函数定义"""
    name: str
    description: str | None = None
    parameters: dict | None = None


class ToolDefinition(BaseModel):
    """OpenAI 格式的工具定义"""
    type: str = "function"
    function: ToolFunction


class ChatCompletionRequest(BaseModel):
    """OpenAI /v1/chat/completions 请求体"""
    model: str = "default"
    messages: list[ChatMessage]
    temperature: float | None = None
    top_p: float | None = None
    n: int = 1
    stream: bool = False
    stop: str | list[str] | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    tools: list[ToolDefinition] | None = None
    tool_choice: str | dict | None = None
    user: str | None = None


# ──────────────────────────────────────────────────────────
# Prompt 构建
# ──────────────────────────────────────────────────────────

def build_agent_prompt(messages: list[ChatMessage]) -> list:
    """
    将 OpenAI messages 格式转换为 LangChain Message 列表

    映射关系：
      OpenAI "system"    → SystemMessage
      OpenAI "user"      → HumanMessage
      OpenAI "assistant" → AIMessage
      OpenAI "tool"      → ToolMessage (from langchain_core.messages)

    支持 tool_calls 转换：OpenAI tool_calls → LangChain tool_calls 格式
    """
    from langchain_core.messages import ToolMessage

    result = []

    for msg in messages:
        if msg.role == "system":
            result.append(SystemMessage(content=msg.content or ""))
        elif msg.role == "user":
            kwargs = {}
            if msg.name:
                kwargs["name"] = msg.name
            result.append(HumanMessage(content=msg.content or "", **kwargs))
        elif msg.role == "assistant":
            kwargs = {}
            if msg.name:
                kwargs["name"] = msg.name
            # 转换 tool_calls
            if msg.tool_calls:
                lc_tool_calls = []
                for tc in msg.tool_calls:
                    lc_tool_calls.append({
                        "id": tc.get("id", str(uuid.uuid4())),
                        "name": tc.get("function", {}).get("name", ""),
                        "args": tc.get("function", {}).get("arguments", {}),
                    })
                kwargs["tool_calls"] = lc_tool_calls
            result.append(AIMessage(content=msg.content or "", **kwargs))
        elif msg.role == "tool":
            result.append(ToolMessage(
                content=msg.content or "",
                tool_call_id=msg.tool_call_id or "",
                name=msg.name or "",
            ))
        else:
            # 未知 role 当作 user 处理
            result.append(HumanMessage(content=msg.content or ""))

    return result


def _generate_run_id() -> str:
    """生成 OpenAI 兼容的 run ID: chatcmpl_{uuid}"""
    return f"chatcmpl_{uuid.uuid4().hex[:29]}"


def _count_tokens_approx(messages: list[ChatMessage]) -> int:
    """粗略估算 token 数（按 4 字符 ≈ 1 token）"""
    total = 0
    for msg in messages:
        if msg.content:
            total += len(msg.content) // 4
    return max(total, 1)


# ──────────────────────────────────────────────────────────
# Non-streaming 响应
# ──────────────────────────────────────────────────────────

async def _handle_non_streaming(req: ChatCompletionRequest) -> JSONResponse:
    """处理非流式请求，返回 chat.completion 对象"""
    run_id = _generate_run_id()
    created = int(time.time())

    try:
        # 将 OpenAI messages 转为内部格式
        lc_messages = build_agent_prompt(req.messages)

        # 提取最后一条 user 消息作为输入
        last_user_msg = ""
        for msg in reversed(req.messages):
            if msg.role == "user" and msg.content:
                last_user_msg = msg.content
                break

        if not last_user_msg:
            return JSONResponse(
                status_code=400,
                content={"error": {"message": "No user message found", "type": "invalid_request_error"}},
            )

        # 使用 AgenticLoopApp 执行推理
        app = get_loop_app()
        user_id = req.user or "openai-compat"
        thread_id = f"openai-{user_id}-{run_id}"

        response_text = await app.chat(
            message=last_user_msg,
            user_id=user_id,
            session_id="openai-compat",
            thread_id=thread_id,
        )

        # 构建 OpenAI 兼容响应
        prompt_tokens = _count_tokens_approx(req.messages)
        completion_tokens = max(len(response_text) // 4, 1)

        response = {
            "id": run_id,
            "object": "chat.completion",
            "created": created,
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"OpenAI compat non-streaming error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(e)[:200],
                    "type": "internal_error",
                }
            },
        )


# ──────────────────────────────────────────────────────────
# Streaming 响应
# ──────────────────────────────────────────────────────────

async def _handle_streaming(req: ChatCompletionRequest) -> StreamingResponse:
    """处理流式请求，返回 SSE chat.completion.chunk 对象"""
    run_id = _generate_run_id()
    created = int(time.time())

    async def event_generator():
        try:
            # 提取最后一条 user 消息
            last_user_msg = ""
            for msg in reversed(req.messages):
                if msg.role == "user" and msg.content:
                    last_user_msg = msg.content
                    break

            if not last_user_msg:
                error_chunk = {
                    "id": run_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": "Error: No user message found"},
                            "finish_reason": "stop",
                        }
                    ],
                }
                yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 发送初始 role chunk
            role_chunk = {
                "id": run_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": ""},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(role_chunk, ensure_ascii=False)}\n\n"

            # 使用 AgenticLoopApp 流式接口
            app = get_loop_app()
            user_id = req.user or "openai-compat"
            thread_id = f"openai-{user_id}-{run_id}"

            full_response = ""
            async for event in app.stream(
                message=last_user_msg,
                user_id=user_id,
                session_id="openai-compat",
                thread_id=thread_id,
            ):
                # 从事件流中提取文本内容
                content = ""
                if isinstance(event, dict):
                    if event.get("error"):
                        content = event.get("message", "")
                    elif event.get("event") == "on_chat_model_stream":
                        data = event.get("data", {})
                        chunk = data.get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            content = chunk.content
                    else:
                        # 尝试从其他事件格式中提取内容
                        data = event.get("data", {})
                        if isinstance(data, dict):
                            chunk = data.get("chunk")
                            if chunk and hasattr(chunk, "content") and chunk.content:
                                content = chunk.content

                if content:
                    full_response += content
                    delta_chunk = {
                        "id": run_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": req.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": content},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(delta_chunk, ensure_ascii=False)}\n\n"

            # 如果流式没有产出内容，用同步接口兜底
            if not full_response:
                response_text = await app.chat(
                    message=last_user_msg,
                    user_id=user_id,
                    session_id="openai-compat",
                    thread_id=thread_id,
                )
                # 按字符分块发送
                chunk_size = 20
                for i in range(0, len(response_text), chunk_size):
                    content = response_text[i:i + chunk_size]
                    delta_chunk = {
                        "id": run_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": req.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": content},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(delta_chunk, ensure_ascii=False)}\n\n"

            # 发送结束 chunk
            finish_chunk = {
                "id": run_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ],
            }
            yield f"data: {json.dumps(finish_chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"OpenAI compat streaming error: {e}", exc_info=True)
            error_chunk = {
                "id": run_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": f"\n\n[Error: {str(e)[:100]}]"},
                        "finish_reason": "stop",
                    }
                ],
            }
            yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────────────────
# 路由处理函数
# ──────────────────────────────────────────────────────────

async def openai_chat_completions(request: Request) -> JSONResponse | StreamingResponse:
    """
    /v1/chat/completions 端点处理函数

    对标 OpenAI API 的 /v1/chat/completions：
    - 支持 streaming (SSE) 和 non-streaming
    - 请求/响应格式与 OpenAI API 完全兼容
    """
    try:
        body = await request.json()
        req = ChatCompletionRequest(**body)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": f"Invalid request: {str(e)[:200]}",
                    "type": "invalid_request_error",
                }
            },
        )

    if not req.messages:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "messages is required and must not be empty",
                    "type": "invalid_request_error",
                }
            },
        )

    if req.stream:
        return await _handle_streaming(req)
    else:
        return await _handle_non_streaming(req)
