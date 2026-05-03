"""
MiniClaw FastAPI Server
Provides REST API for MiniClaw services
"""

import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

from miniclaw.core.graph import MiniClawApp
from miniclaw.utils.helpers import init_data_dirs, format_datetime, get_weekday_name
from miniclaw.tools.reminder import (
    reminder_manager,
    web_notification,
    notification_service,
)
from miniclaw.tools.scheduler import scheduler
from miniclaw.tools.weather import fetch_weather, get_weather_suggestion
from miniclaw.tools.news import fetch_news
from miniclaw.config.settings import settings


app_state = {"miniclaw_app": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_data_dirs()
    
    app_state["miniclaw_app"] = MiniClawApp()
    
    logger.info("MiniClaw API started")
    yield
    
    scheduler.stop()
    logger.info("MiniClaw API stopped")


app = FastAPI(
    title="MiniClaw API",
    description="MiniClaw - Personal AI Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    user_id: str = Field(default="default", description="User ID")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    thread_id: Optional[str] = Field(default=None, description="Thread ID for conversation continuity")
    force_think: bool = Field(default=False, description="Force enable deep thinking")
    force_search: bool = Field(default=False, description="Force enable web search")


class ChatResponse(BaseModel):
    response: str
    intent: Optional[str] = None
    timestamp: str


class ReminderRequest(BaseModel):
    reminder_type: str = Field(..., description="Type of reminder")
    message: str = Field(..., description="Reminder message")
    interval_minutes: Optional[int] = Field(default=60, description="Interval in minutes")


class WeatherRequest(BaseModel):
    city: str = Field(..., description="City name")


class NewsRequest(BaseModel):
    category: str = Field(default="all", description="News category")
    count: int = Field(default=5, description="Number of news items")


class SessionCreateRequest(BaseModel):
    title: str = Field(default="新会话", description="Session title")


class SessionRenameRequest(BaseModel):
    title: str = Field(..., description="New session title")


class FileRequest(BaseModel):
    path: str = Field(..., description="File path")
    content: Optional[str] = Field(default=None, description="File content for write")


class ConfigRagModeRequest(BaseModel):
    enabled: bool = Field(..., description="Enable or disable RAG mode")


def get_miniclaw_app() -> MiniClawApp:
    if app_state["miniclaw_app"] is None:
        app_state["miniclaw_app"] = MiniClawApp()
    return app_state["miniclaw_app"]


# Session storage (in-memory with file persistence)
_sessions: Dict[str, Dict[str, Any]] = {}
_session_messages: Dict[str, List[Dict[str, Any]]] = {}


def _get_session_file() -> Path:
    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "sessions.json"


def _load_sessions():
    global _sessions, _session_messages
    session_file = _get_session_file()
    if session_file.exists():
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            _sessions = data.get("sessions", {})
            _session_messages = data.get("messages", {})
        except Exception as e:
            logger.warning(f"Failed to load sessions: {e}")


def _save_sessions():
    session_file = _get_session_file()
    try:
        session_file.write_text(
            json.dumps(
                {"sessions": _sessions, "messages": _session_messages},
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"Failed to save sessions: {e}")


# 节点详细描述映射
NODE_DESCRIPTIONS = {
    "rag_detect": {
        "title": "检索增强检测",
        "description": "分析用户问题是否需要检索外部知识库",
        "details": "检查问题是否涉及需要查询文档、知识库或外部信息的场景",
    },
    "supervisor": {
        "title": "智能路由决策",
        "description": "分析用户意图并选择最合适的专业助手",
        "details": "基于用户问题的类型和上下文，决策分配给哪个专业 Agent 处理",
    },
    "chat": {
        "title": "对话助手",
        "description": "处理日常对话和通用问题",
        "details": "负责日常聊天、问候、简单问答、情感交流等通用对话场景",
    },
    "info": {
        "title": "信息查询助手",
        "description": "查询天气、新闻等实时信息",
        "details": "调用天气、新闻等工具获取实时信息，回答用户的事实性问题",
    },
    "health": {
        "title": "健康顾问",
        "description": "提供健康建议和作息管理",
        "details": "分析用户的健康相关问题，提供休息提醒、作息建议等健康管理方案",
    },
    "learning": {
        "title": "学习规划师",
        "description": "制定学习计划和知识追踪",
        "details": "根据用户需求制定个性化学习计划，追踪学习进度，推荐学习资源",
    },
    "task": {
        "title": "任务管理助手",
        "description": "管理待办事项和提醒",
        "details": "帮助用户创建、管理和追踪任务，设置提醒，优化任务安排",
    },
    "data": {
        "title": "数据处理助手",
        "description": "处理 Excel 和数据分析",
        "details": "协助用户进行 Excel 操作、数据分析、图表生成等数据处理任务",
    },
}


def _get_node_description(node_name: str, action: str = "start") -> str:
    """获取节点的详细描述"""
    node_info = NODE_DESCRIPTIONS.get(node_name, {})
    if not node_info:
        return f"正在调用 {node_name}..."
    
    if action == "start":
        return f"{node_info['title']}：{node_info['description']}"
    else:
        return f"{node_info['title']}：{node_info['details']}"


_load_sessions()


@app.get("/")
async def root():
    return {
        "name": "MiniClaw API",
        "version": "0.1.0",
        "status": "running",
        "timestamp": format_datetime(),
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": format_datetime(),
        "weekday": get_weekday_name(),
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        miniclaw = get_miniclaw_app()
        
        response = await miniclaw.chat(
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id or "default",
            thread_id=request.thread_id or request.user_id,
            force_think=request.force_think,
            force_search=request.force_search,
        )
        
        return ChatResponse(
            response=response,
            timestamp=format_datetime(),
        )
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    miniclaw = get_miniclaw_app()
    session_id = request.session_id or "default"
    
    async def event_generator():
        full_content = ""
        thinking_content = ""
        current_agent = ""
        in_supervisor = False
        
        # 确保 session 存在（兼容默认 session）
        if session_id not in _sessions:
            now = datetime.now().timestamp()
            _sessions[session_id] = {
                "title": request.message[:20] + "..." if len(request.message) > 20 else request.message,
                "created_at": now,
                "updated_at": now,
            }
            _session_messages[session_id] = []
            _save_sessions()
        
        # 保存用户消息
        _session_messages[session_id].append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat(),
        })
        _sessions[session_id]["updated_at"] = datetime.now().timestamp()
        _save_sessions()
        
        try:
            # 发送开始事件
            yield f"event: start\ndata: {json.dumps({'session_id': session_id})}\n\n"
            
            async for event in miniclaw.stream(
                message=request.message,
                user_id=request.user_id,
                session_id=session_id,
                thread_id=request.thread_id or request.user_id,
                force_think=request.force_think,
                force_search=request.force_search,
            ):
                # logger.info(f"ALL EVENT: {type(event).__name__} = {event}")
                if isinstance(event, dict):
                    if event.get("error"):
                        yield f"event: error\ndata: {json.dumps({'error': event.get('message', 'Unknown error'), 'details': event.get('details', '')})}\n\n"
                        continue
                    
                    event_type = event.get("event")
                    event_name = event.get("name", "")
                    # logger.info(f"[SSE] event_type={event_type}, name={event_name}")
                    
                    # 节点开始执行 - 发送思考过程
                    if event_type in ("on_chain_start", "on_chat_model_start"):
                        node_name = event_name
                        # 过滤内部节点、LangGraph框架节点和LLM模型事件
                        skip_nodes = {"__start__", "__end__", "RunnableSequence", "Unnamed", "LangGraph", "should_retrieve"}
                        if node_name not in skip_nodes:
                            logger.info(f"✅ 输出 thinking: {node_name}")  # 看是否执行到这里
                        # 跳过 LLM 模型事件（如 ChatOllama, ChatOpenAI）
                        if node_name and node_name not in skip_nodes and not node_name.startswith("Chat"):
                            # 追踪 supervisor 节点进入
                            if node_name == "supervisor":
                                in_supervisor = True
                            current_agent = node_name
                            # 使用详细描述
                            description = _get_node_description(node_name, "start")
                            yield f"event: thinking\ndata: {json.dumps({'step': node_name, 'status': 'start', 'message': description})}\n\n"
                    
                    # 节点结束执行
                    elif event_type in ("on_chain_end", "on_chat_model_end"):
                        node_name = event_name
                        skip_nodes = {"__start__", "__end__", "RunnableSequence", "Unnamed", "LangGraph", "should_retrieve"}
                        # 跳过 LLM 模型事件（如 ChatOllama, ChatOpenAI）
                        if node_name and node_name not in skip_nodes and not node_name.startswith("Chat"):
                            # 追踪 supervisor 节点退出
                            if node_name == "supervisor":
                                in_supervisor = False
                            
                            # 提取 Supervisor 决策原因
                            thinking_message = _get_node_description(node_name, "end")
                            if node_name == "supervisor":
                                data = event.get("data", {})
                                output = data.get("output", {})
                                if hasattr(output, "update") and callable(getattr(output, "update", None)) is False:
                                    update_data = output.update
                                    if isinstance(update_data, dict):
                                        reason = update_data.get("supervisor_reason", "")
                                        next_agent = update_data.get("next_agent", "")
                                        if reason:
                                            thinking_message = f"决策分析：{reason}\n→ 路由到：{next_agent}"
                                elif isinstance(output, dict):
                                    reason = output.get("supervisor_reason", "")
                                    next_agent = output.get("next_agent", "")
                                    if reason:
                                        thinking_message = f"决策分析：{reason}\n→ 路由到：{next_agent}"
                            
                            yield f"event: thinking\ndata: {json.dumps({'step': node_name, 'status': 'end', 'message': thinking_message})}\n\n"
                            
                            # 提取节点输出内容（对于非流式调用的 agent）
                            if node_name != "supervisor":
                                data = event.get("data", {})
                                output = data.get("output", {})
                                # logger.info(f"[SSE] Extracting content from {node_name}, output type={type(output)}, output={output}")
                                # 处理 Command 对象
                                if hasattr(output, "update") and callable(getattr(output, "update", None)) is False:
                                    # 确保 update 是属性而不是方法
                                    update_data = output.update
                                    if isinstance(update_data, dict):
                                        messages = update_data.get("messages", [])
                                        for msg in messages:
                                            if hasattr(msg, "content") and msg.content:
                                                if msg.content != full_content:
                                                    full_content = msg.content
                                                    yield f"event: token\ndata: {json.dumps({'content': msg.content})}\n\n"
                                # 处理普通消息列表
                                elif isinstance(output, list):
                                    for msg in output:
                                        if hasattr(msg, "content") and msg.content:
                                            if msg.content != full_content:
                                                full_content = msg.content
                                                yield f"event: token\ndata: {json.dumps({'content': msg.content})}\n\n"
                                # 处理字典格式
                                elif isinstance(output, dict):
                                    messages = output.get("messages", [])
                                    for msg in messages:
                                        if hasattr(msg, "content") and msg.content:
                                            if msg.content != full_content:
                                                full_content = msg.content
                                                yield f"event: token\ndata: {json.dumps({'content': msg.content})}\n\n"
                    
                    # 流式 token
                    elif event_type == "on_chat_model_stream":
                        data = event.get("data", {})
                        chunk = data.get("chunk", {})
                        content = ""
                        if hasattr(chunk, "content"):
                            content = chunk.content
                        elif isinstance(chunk, dict):
                            content = chunk.get("content", "")
                        if content:
                            # 在 Supervisor 节点内，收集思考内容
                            if in_supervisor:
                                thinking_content += content
                                # 实时发送思考内容到前端
                                yield f"event: thinking\ndata: {json.dumps({'step': 'supervisor', 'status': 'thinking', 'message': content, 'is_thinking_content': True})}\n\n"
                                continue
                            full_content += content
                            yield f"event: token\ndata: {json.dumps({'content': content})}\n\n"
                    
                    # 工具调用开始
                    elif event_type == "on_tool_start":
                        tool_name = event_name
                        tool_input = event.get("data", {}).get("input", {})
                        yield f"event: tool_start\ndata: {json.dumps({'tool': tool_name, 'input': str(tool_input)})}\n\n"
                    
                    # 工具调用结束
                    elif event_type == "on_tool_end":
                        tool_name = event_name
                        tool_output = event.get("data", {}).get("output", "")
                        yield f"event: tool_end\ndata: {json.dumps({'tool': tool_name, 'output': str(tool_output)})}\n\n"
                    
                    # 其他事件作为思考过程
                    elif event_type and event_type.startswith("on_"):
                        pass  # 忽略其他内部事件
                    else:
                        # 非标准事件，可能是自定义事件
                        yield f"event: message\ndata: {json.dumps({'event': event_type, 'data': str(event)})}\n\n"
                else:
                    # 非字典事件（图节点输出）
                    # logger.info(f"[NODE OUTPUT] keys={list(event.keys()) if hasattr(event, 'keys') else 'N/A'}")
                    for node_name, node_data in event.items():
                        logger.info(f"[NODE] {node_name}: {node_data}")
                        # 跳过框架内部节点和 Supervisor 节点
                        skip_nodes = {"supervisor", "LangGraph", "__start__", "__end__"}
                        if node_name in skip_nodes:
                            continue
                        # 优先提取 agent_response 字段（Worker 返回的最终回复）
                        if isinstance(node_data, dict):
                            agent_response = node_data.get("agent_response", "")
                            if agent_response and agent_response != full_content:
                                full_content = agent_response
                                yield f"event: token\ndata: {json.dumps({'content': agent_response})}\n\n"
                                continue
                            # 回退到 messages 字段，但只提取 AI 消息
                            if "messages" in node_data:
                                for msg in node_data["messages"]:
                                    if hasattr(msg, "content") and msg.content:
                                        # 跳过人类消息（避免把用户输入当成回复）
                                        if hasattr(msg, "type") and msg.type == "human":
                                            continue
                                        if not full_content or msg.content != full_content:
                                            full_content = msg.content
                                            yield f"event: token\ndata: {json.dumps({'content': msg.content})}\n\n"
        except Exception as e:
            logger.error(f"Event generator error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            # 保存 AI 回复
            if full_content and session_id in _session_messages:
                _session_messages[session_id].append({
                    "role": "assistant",
                    "content": full_content,
                    "timestamp": datetime.now().isoformat(),
                })
                _sessions[session_id]["updated_at"] = datetime.now().timestamp()
                _save_sessions()
            
            # 发送完成事件，确保连接正常结束
            yield f"event: done\ndata: {json.dumps({'content': full_content})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/weather")
async def get_weather(city: str = "Beijing"):
    try:
        weather = fetch_weather(city)
        suggestion = get_weather_suggestion(weather)
        
        return {
            "weather": weather,
            "suggestion": suggestion,
            "timestamp": format_datetime(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/news")
async def get_news(category: str = "all", count: int = 5):
    try:
        news = fetch_news(category, count)
        return {
            "news": news,
            "count": len(news),
            "timestamp": format_datetime(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reminders")
async def create_reminder(request: ReminderRequest):
    from miniclaw.tools.reminder import ReminderType
    
    reminder_id = f"reminder_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    reminder = reminder_manager.create_reminder(
        reminder_id=reminder_id,
        reminder_type=ReminderType(request.reminder_type),
        message=request.message,
        interval_minutes=request.interval_minutes,
    )
    
    return {
        "success": True,
        "reminder": reminder,
    }


@app.get("/reminders")
async def get_reminders():
    reminders = reminder_manager.get_all_reminders()
    return {
        "reminders": reminders,
        "count": len(reminders),
    }


@app.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str):
    success = reminder_manager.delete_reminder(reminder_id)
    if not success:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"success": True}


@app.get("/notifications")
async def get_notifications(unread_only: bool = False):
    notifications = web_notification.get_notifications(unread_only)
    return {
        "notifications": notifications,
        "count": len(notifications),
    }


@app.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    success = web_notification.mark_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@app.get("/scheduler/jobs")
async def get_scheduler_jobs():
    jobs = scheduler.get_jobs()
    return {
        "jobs": jobs,
        "count": len(jobs),
    }


@app.post("/scheduler/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    success = scheduler.pause_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True}


@app.post("/scheduler/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    success = scheduler.resume_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True}


# Session management endpoints
@app.get("/sessions")
async def get_sessions():
    session_list = []
    for sid, sdata in _sessions.items():
        msg_count = len(_session_messages.get(sid, []))
        session_list.append({
            "id": sid,
            "title": sdata.get("title", "新会话"),
            "created_at": sdata.get("created_at", 0),
            "updated_at": sdata.get("updated_at", 0),
            "message_count": msg_count,
        })
    session_list.sort(key=lambda x: x["updated_at"], reverse=True)
    return session_list


@app.post("/sessions")
async def post_session(request: SessionCreateRequest):
    sid = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"
    now = datetime.now().timestamp()
    _sessions[sid] = {
        "title": request.title,
        "created_at": now,
        "updated_at": now,
    }
    _session_messages[sid] = []
    _save_sessions()
    return {
        "id": sid,
        "title": request.title,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }


@app.get("/sessions/{session_id}/history")
async def get_session_history_endpoint(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = _session_messages.get(session_id, [])
    return {
        "id": session_id,
        "title": _sessions[session_id].get("title", "新会话"),
        "created_at": _sessions[session_id].get("created_at", 0),
        "updated_at": _sessions[session_id].get("updated_at", 0),
        "messages": messages,
    }


@app.put("/sessions/{session_id}")
async def put_session(session_id: str, request: SessionRenameRequest):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    _sessions[session_id]["title"] = request.title
    _sessions[session_id]["updated_at"] = datetime.now().timestamp()
    _save_sessions()
    return {
        "id": session_id,
        "title": request.title,
        "created_at": _sessions[session_id].get("created_at", 0),
        "updated_at": _sessions[session_id].get("updated_at", 0),
        "message_count": len(_session_messages.get(session_id, [])),
    }


@app.delete("/sessions/{session_id}")
async def del_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]
    if session_id in _session_messages:
        del _session_messages[session_id]
    _save_sessions()
    return {"ok": True}


# Skills endpoint
@app.get("/skills")
async def get_skills():
    skills_dir = Path(settings.SKILLS_DIR)
    skills = []
    if skills_dir.exists():
        for f in skills_dir.iterdir():
            if f.suffix == ".py":
                try:
                    rel = str(f.relative_to(Path.cwd()))
                except ValueError:
                    rel = str(f)
                skills.append({
                    "name": f.stem,
                    "description": f"Skill: {f.stem}",
                    "path": rel,
                })
    return skills


# File endpoints
@app.get("/files")
async def get_file(path: str = Query(..., description="File path")):
    try:
        file_path = Path(path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        content = file_path.read_text(encoding="utf-8")
        return {"path": path, "content": content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/files")
async def post_file(request: FileRequest):
    try:
        file_path = Path(request.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(request.content or "", encoding="utf-8")
        return {"ok": True, "path": request.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Config endpoints
@app.get("/config/rag-mode")
async def get_rag_mode():
    return {"enabled": True}


@app.put("/config/rag-mode")
async def put_rag_mode(request: ConfigRagModeRequest):
    return {"enabled": request.enabled}
