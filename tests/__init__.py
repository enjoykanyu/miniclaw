"""
MiniClaw Tests
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock


class TestState:
    def test_create_initial_state(self):
        from miniclaw.core.state import create_initial_state
        
        state = create_initial_state("test_user", "test_session")
        
        assert state["user_id"] == "test_user"
        assert state["session_id"] == "test_session"
        assert state["messages"] == []
        assert state["intent"] is None


class TestRouter:
    def test_detect_intent_by_keywords(self):
        from miniclaw.core.router import detect_intent_by_keywords
        
        assert detect_intent_by_keywords("帮我制定一个学习计划") == "learning"
        assert detect_intent_by_keywords("今天天气怎么样") == "info"
        assert detect_intent_by_keywords("创建一个任务") == "task"
        assert detect_intent_by_keywords("提醒我休息") == "health"
        assert detect_intent_by_keywords("新建Excel表格") == "data"
        assert detect_intent_by_keywords("你好") == "chat"


class TestExcelTools:
    def test_create_excel(self, tmp_path):
        from miniclaw.tools.excel import create_excel
        from miniclaw.config.settings import settings
        
        settings.EXCEL_DIR = str(tmp_path)
        
        filepath = create_excel(
            "test_file",
            ["列1", "列2", "列3"],
            [["a", "b", "c"]],
        )
        
        assert "test_file.xlsx" in filepath


class TestWeatherTools:
    @patch("miniclaw.tools.weather.httpx.Client")
    def test_fetch_weather_no_api_key(self, mock_client):
        from miniclaw.tools.weather import fetch_weather
        from miniclaw.config.settings import settings
        
        settings.WEATHER_API_KEY = None
        
        result = fetch_weather("Beijing")
        
        assert result["city"] == "Beijing"
        assert "API未配置" in result.get("message", "") or result.get("condition") == "API未配置"


class TestNewsTools:
    def test_fetch_news_no_api_key(self):
        from miniclaw.tools.news import fetch_news
        from miniclaw.config.settings import settings
        
        settings.NEWS_API_KEY = None
        
        result = fetch_news()
        
        assert len(result) > 0
        assert "API未配置" in result[0].get("title", "") or "未配置" in result[0].get("summary", "")


class TestScheduler:
    def test_scheduler_singleton(self):
        from miniclaw.tools.scheduler import SchedulerService
        
        s1 = SchedulerService()
        s2 = SchedulerService()
        
        assert s1 is s2


class TestReminder:
    def test_reminder_manager(self):
        from miniclaw.tools.reminder import reminder_manager, ReminderType
        
        reminder = reminder_manager.create_reminder(
            reminder_id="test_reminder",
            reminder_type=ReminderType.STANDUP,
            message="Test reminder",
        )
        
        assert reminder["id"] == "test_reminder"
        assert reminder["type"] == "standup"
        
        reminders = reminder_manager.get_all_reminders()
        assert len(reminders) > 0
        
        reminder_manager.delete_reminder("test_reminder")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
