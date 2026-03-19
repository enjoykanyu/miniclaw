"""
MiniClaw FastAPI Server
Provides REST API for MiniClaw services
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
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


def get_miniclaw_app() -> MiniClawApp:
    if app_state["miniclaw_app"] is None:
        app_state["miniclaw_app"] = MiniClawApp()
    return app_state["miniclaw_app"]


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
    
    from fastapi.responses import StreamingResponse
    import json
    
    async def event_generator():
        async for event in miniclaw.stream(
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id or "default",
            thread_id=request.thread_id or request.user_id,
        ):
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    for msg in node_data["messages"]:
                        if hasattr(msg, "content"):
                            yield f"data: {json.dumps({'content': msg.content})}\n\n"
    
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
