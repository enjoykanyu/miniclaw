"""
MiniClaw Scheduler Service
Handles scheduled tasks and reminders using APScheduler
"""

from typing import Callable, Optional, Dict, Any
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore

from miniclaw.config.settings import settings


class SchedulerService:
    _instance: Optional["SchedulerService"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._scheduler = None
            cls._instance._jobs: Dict[str, Any] = {}
        return cls._instance
    
    @property
    def scheduler(self) -> AsyncIOScheduler:
        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler(
                jobstores={"default": MemoryJobStore()},
                timezone="Asia/Shanghai",
            )
        return self._scheduler
    
    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
    
    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
    
    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        minutes: int = 60,
        **kwargs,
    ) -> str:
        self.scheduler.add_job(
            func,
            trigger=IntervalTrigger(minutes=minutes),
            id=job_id,
            replace_existing=True,
            kwargs=kwargs,
        )
        self._jobs[job_id] = {
            "type": "interval",
            "minutes": minutes,
            "created_at": datetime.now().isoformat(),
        }
        return job_id
    
    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        hour: int,
        minute: int = 0,
        **kwargs,
    ) -> str:
        self.scheduler.add_job(
            func,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=job_id,
            replace_existing=True,
            kwargs=kwargs,
        )
        self._jobs[job_id] = {
            "type": "cron",
            "hour": hour,
            "minute": minute,
            "created_at": datetime.now().isoformat(),
        }
        return job_id
    
    def add_daily_job(
        self,
        job_id: str,
        func: Callable,
        time_str: str,
        **kwargs,
    ) -> str:
        hour, minute = map(int, time_str.split(":"))
        return self.add_cron_job(job_id, func, hour, minute, **kwargs)
    
    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self.scheduler.remove_job(job_id)
            del self._jobs[job_id]
            return True
        return False
    
    def get_jobs(self) -> Dict[str, Any]:
        return self._jobs.copy()
    
    def pause_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self.scheduler.pause_job(job_id)
            return True
        return False
    
    def resume_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self.scheduler.resume_job(job_id)
            return True
        return False


scheduler = SchedulerService()


def setup_default_reminders(
    morning_callback: Optional[Callable] = None,
    noon_callback: Optional[Callable] = None,
    night_callback: Optional[Callable] = None,
    standup_callback: Optional[Callable] = None,
):
    scheduler.start()
    
    if morning_callback:
        hour, minute = map(int, settings.MORNING_GREETING_TIME.split(":"))
        scheduler.add_cron_job("morning_greeting", morning_callback, hour, minute)
    
    if noon_callback:
        hour, minute = map(int, settings.NOON_REMINDER_TIME.split(":"))
        scheduler.add_cron_job("noon_reminder", noon_callback, hour, minute)
    
    if night_callback:
        hour, minute = map(int, settings.NIGHT_REMINDER_TIME.split(":"))
        scheduler.add_cron_job("night_reminder", night_callback, hour, minute)
    
    if standup_callback:
        scheduler.add_interval_job(
            "standup_reminder",
            standup_callback,
            minutes=settings.STANDUP_INTERVAL_MINUTES,
        )
    
    return scheduler
