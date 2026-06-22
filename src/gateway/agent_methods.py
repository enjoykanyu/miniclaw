"""
Gateway Agent Methods

对标 OpenClaw 的 Gateway Agent 集成：
  - agent.run: 执行 Agentic Loop 推理（含 runId 幂等去重）
  - agent.list: 列出可用 Agent
  - agent.status: 查询 Agent 状态

这些方法注册到 Gateway 的 _METHOD_REGISTRY，
通过 WebSocket 帧协议 (req/res/event) 提供服务。
"""

import time
from typing import Any, Dict, Optional
from loguru import logger

from agent_loop.app import AgenticLoopApp
from gateway.lanes import CommandLane, get_lane_manager


_loop_app: Optional[AgenticLoopApp] = None


def get_loop_app() -> AgenticLoopApp:
    global _loop_app
    if _loop_app is None:
        _loop_app = AgenticLoopApp()
    return _loop_app


async def handle_agent_run(params: dict, auth: dict) -> dict:
    """
    agent.run 方法处理器

    对标 OpenClaw 的 agentCommand：
    接收用户消息，执行 Agentic Loop 推理，返回结果。

    请求帧:
    {
      "type": "req",
      "method": "agent.run",
      "id": "...",
      "params": {
        "message": "用户消息",
        "user_id": "default",
        "session_id": "default",
        "thread_id": "default",
        "force_think": false,
        "force_search": false,
        "selected_kbs": null,
        "kb_retrieval_mode": "intent"
      }
    }

    响应帧:
    {
      "type": "res",
      "id": "...",
      "ok": true,
      "payload": {
        "response": "助手回复",
        "agent": "chat",
        "loop_iterations": 3,
        "tool_calls": 2
      }
    }
    """
    message = params.get("message", "")
    if not message:
        return {
            "response": "",
            "error": "message is required",
        }

    user_id = params.get("user_id", "default")
    session_id = params.get("session_id", "default")
    thread_id = params.get("thread_id", f"ws-{user_id}-{session_id}")
    force_think = params.get("force_think", False)
    force_search = params.get("force_search", False)
    selected_kbs = params.get("selected_kbs")
    kb_retrieval_mode = params.get("kb_retrieval_mode", "intent")
    run_id = params.get("run_id", "")

    # ── runId 幂等去重（对标 OpenClaw DedupeCache）──
    if run_id:
        from gateway.dedupe import resolve_global_dedupe_cache
        dedupe = resolve_global_dedupe_cache()
        now = time.time()
        cached = dedupe.peek(run_id, now)
        if cached is not None:
            logger.info(f"agent.run: dedupe hit for run_id={run_id}, returning cached result")
            return cached

    logger.info(f"agent.run: message={message[:50]}... user={user_id}")

    try:
        app = get_loop_app()
        session_key = f"{user_id}:{session_id}"

        # ── 通过 Main Lane 执行，实现会话级并发控制 ──
        lane_manager = get_lane_manager()

        async def _run_agent():
            return await app.chat(
                message=message,
                user_id=user_id,
                session_id=session_id,
                thread_id=thread_id,
                force_think=force_think,
                force_search=force_search,
                selected_kbs=selected_kbs,
                kb_retrieval_mode=kb_retrieval_mode,
            )

        response = await lane_manager.enqueue_command_in_lane(
            lane=CommandLane.MAIN,
            session_key=session_key,
            coro=_run_agent(),
        )

        result = {
            "response": response,
            "agent": "agentic_loop",
            "status": "completed",
        }

        # ── 缓存结果到 DedupeCache（对标 OpenClaw runId 去重）──
        if run_id:
            try:
                from gateway.dedupe import resolve_global_dedupe_cache
                dedupe = resolve_global_dedupe_cache()
                dedupe.check(run_id, time.time(), value=result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"agent.run failed: {e}", exc_info=True)
        error_result = {
            "response": f"处理请求时出现错误: {str(e)[:100]}",
            "error": str(e),
            "status": "failed",
        }

        # ── 错误结果也缓存（防止重复失败请求）──
        if run_id:
            try:
                from gateway.dedupe import resolve_global_dedupe_cache
                dedupe = resolve_global_dedupe_cache()
                dedupe.check(run_id, time.time(), value=error_result)
            except Exception:
                pass

        return error_result


async def handle_agent_list(params: dict, auth: dict) -> dict:
    """
    agent.list 方法处理器

    列出所有可用的 Worker Agent 及其描述。
    """
    agents = [
        {"name": "learning", "description": "学习规划助手，帮助制定学习计划、追踪进度、安排复习"},
        {"name": "task", "description": "任务管理助手，管理TODO清单、创建任务、生成每日报告"},
        {"name": "info", "description": "信息获取助手，查询天气、推送新闻、知识问答"},
        {"name": "health", "description": "健康提醒助手，定时提醒休息、管理作息、提供健康建议"},
        {"name": "data", "description": "数据处理助手，操作Excel表格、数据分析"},
        {"name": "chat", "description": "日常聊天助手，处理一般对话和引导用户使用功能"},
    ]
    return {"agents": agents, "total": len(agents)}


async def handle_agent_status(params: dict, auth: dict) -> dict:
    """
    agent.status 方法处理器

    查询 Agentic Loop 的运行状态。
    """
    return {
        "status": "ready",
        "loop_app_initialized": _loop_app is not None,
        "features": {
            "rag": True,
            "compaction": True,
            "loop_detection": True,
            "model_fallback": True,
        },
    }


def register_agent_methods():
    """
    注册所有 Agent 相关的 Gateway 方法

    在 Gateway 启动时调用，将 agent.* 方法注册到 _METHOD_REGISTRY。
    """
    from gateway.server_impl import register_method

    register_method("agent.run", handle_agent_run, required_role="user")
    register_method("agent.list", handle_agent_list, required_role="user")
    register_method("agent.status", handle_agent_status, required_role="user")

    logger.info("Agent methods registered: agent.run, agent.list, agent.status")
