"""
MiniClaw Reminder Tools
Handles push notifications and reminders
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from miniclaw.utils.helpers import format_datetime


class ReminderType(str, Enum):
    STANDUP = "standup"
    WATER = "water"
    EYE_EXERCISE = "eye_exercise"
    BREAK = "break"
    TASK = "task"
    STUDY = "study"
    CUSTOM = "custom"


class ReminderManager:
    def __init__(self):
        self._reminders: Dict[str, Dict[str, Any]] = {}
    
    def create_reminder(
        self,
        reminder_id: str,
        reminder_type: ReminderType,
        message: str,
        scheduled_time: Optional[datetime] = None,
        interval_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        reminder = {
            "id": reminder_id,
            "type": reminder_type.value,
            "message": message,
            "scheduled_time": scheduled_time.isoformat() if scheduled_time else None,
            "interval_minutes": interval_minutes,
            "is_sent": False,
            "created_at": format_datetime(),
            "last_sent_at": None,
        }
        self._reminders[reminder_id] = reminder
        return reminder
    
    def get_reminder(self, reminder_id: str) -> Optional[Dict[str, Any]]:
        return self._reminders.get(reminder_id)
    
    def get_all_reminders(self) -> List[Dict[str, Any]]:
        return list(self._reminders.values())
    
    def mark_sent(self, reminder_id: str) -> bool:
        if reminder_id in self._reminders:
            self._reminders[reminder_id]["is_sent"] = True
            self._reminders[reminder_id]["last_sent_at"] = format_datetime()
            return True
        return False
    
    def delete_reminder(self, reminder_id: str) -> bool:
        if reminder_id in self._reminders:
            del self._reminders[reminder_id]
            return True
        return False


reminder_manager = ReminderManager()


class NotificationChannel:
    async def send(self, title: str, message: str, **kwargs) -> bool:
        raise NotImplementedError


class WebNotificationChannel(NotificationChannel):
    def __init__(self):
        self._notifications: List[Dict[str, Any]] = []
    
    async def send(self, title: str, message: str, **kwargs) -> bool:
        notification = {
            "id": f"notif_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "title": title,
            "message": message,
            "read": False,
            "created_at": format_datetime(),
            **kwargs,
        }
        self._notifications.append(notification)
        return True
    
    def get_notifications(self, unread_only: bool = False) -> List[Dict[str, Any]]:
        if unread_only:
            return [n for n in self._notifications if not n["read"]]
        return self._notifications.copy()
    
    def mark_read(self, notification_id: str) -> bool:
        for notif in self._notifications:
            if notif["id"] == notification_id:
                notif["read"] = True
                return True
        return False
    
    def clear_all(self):
        self._notifications.clear()


web_notification = WebNotificationChannel()


class WeComChannel(NotificationChannel):
    async def send(self, title: str, message: str, **kwargs) -> bool:
        return False


class DingTalkChannel(NotificationChannel):
    async def send(self, title: str, message: str, **kwargs) -> bool:
        return False


class FeishuChannel(NotificationChannel):
    async def send(self, title: str, message: str, **kwargs) -> bool:
        return False


class NotificationService:
    def __init__(self):
        self._channels: Dict[str, NotificationChannel] = {
            "web": web_notification,
            "wecom": WeComChannel(),
            "dingtalk": DingTalkChannel(),
            "feishu": FeishuChannel(),
        }
    
    def register_channel(self, name: str, channel: NotificationChannel):
        self._channels[name] = channel
    
    async def notify(
        self,
        title: str,
        message: str,
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, bool]:
        results = {}
        target_channels = channels or ["web"]
        
        for channel_name in target_channels:
            if channel_name in self._channels:
                try:
                    success = await self._channels[channel_name].send(title, message, **kwargs)
                    results[channel_name] = success
                except Exception:
                    results[channel_name] = False
        
        return results


notification_service = NotificationService()
