"""
MiniClaw Skill System
Provides pluggable, modular skill system with enable/disable functionality
"""

from typing import Dict, Any, Callable, Optional, List
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
import importlib.util
import yaml
from datetime import datetime
import random

from miniclaw.skills import skill, SkillRegistry, skill_registry

__all__ = [
    "skill",
    "SkillRegistry",
    "skill_registry",
    "WeatherSkill",
    "NewsSkill",
    "ReminderSkill",
    "PDFSkill",
    "SummarySkill",
    "EmotionSkill",
    "JokeSkill",
    "CalendarSkill",
    "SkillConfig",
    "get_enabled_skills",
    "is_skill_enabled",
]


class SkillConfig:
    _instance: Optional["SkillConfig"] = None
    _enabled_skills: Dict[str, bool] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._enabled_skills = {
                "weather": True,
                "news": True,
                "reminder": True,
                "pdf": True,
                "summary": True,
                "emotion": True,
                "joke": True,
                "calendar": True,
            }
        return cls._instance
    
    def enable_skill(self, skill_name: str) -> bool:
        if skill_registry.get(skill_name):
            self._enabled_skills[skill_name] = True
            return True
        return False
    
    def disable_skill(self, skill_name: str) -> bool:
        if skill_name in self._enabled_skills:
            self._enabled_skills[skill_name] = False
            return True
        return False
    
    def get_enabled_skills(self) -> List[str]:
        return [name for name, enabled in self._enabled_skills.items() if enabled]
    
    def is_skill_enabled(self, skill_name: str) -> bool:
        return self._enabled_skills.get(skill_name, False)
    
    def toggle_skill(self, skill_name: str) -> bool:
        if skill_name in self._enabled_skills:
            self._enabled_skills[skill_name] = not self._enabled_skills[skill_name]
            return True
        return False


skill_config = SkillConfig()


def get_enabled_skills() -> List[str]:
    return skill_config.get_enabled_skills()


def is_skill_enabled(skill_name: str) -> bool:
    return skill_config.is_skill_enabled(skill_name)


@skill("weather", "天气查询技能，获取天气信息和出行建议")
class WeatherSkill:
    @staticmethod
    def get_weather(city: str) -> dict:
        from miniclaw.tools.weather import fetch_weather
        return fetch_weather(city)
    
    @staticmethod
    def get_forecast(city: str, days: int = 3) -> list:
        from miniclaw.tools.weather import fetch_weather
        weather = fetch_weather(city)
        return [weather]
    
    @staticmethod
    def get_suggestion(city: str) -> str:
        from miniclaw.tools.weather import fetch_weather, get_weather_suggestion
        weather = fetch_weather(city)
        return get_weather_suggestion(weather)


@skill("news", "新闻推送技能，获取最新新闻和摘要")
class NewsSkill:
    @staticmethod
    def get_headlines(category: str = "all", count: int = 5) -> list:
        from miniclaw.tools.news import fetch_news
        return fetch_news(category, count)
    
    @staticmethod
    def search_news(query: str) -> list:
        from miniclaw.rag.news_enhancer import NewsEnhancer
        enhancer = NewsEnhancer()
        return enhancer.search_news_history(query)
    
    @staticmethod
    def get_digest(category: str = "all", count: int = 5) -> str:
        from miniclaw.rag.news_enhancer import NewsEnhancer
        enhancer = NewsEnhancer()
        return enhancer.get_news_digest(category, count)


@skill("reminder", "提醒管理技能，创建和管理提醒事项")
class ReminderSkill:
    @staticmethod
    def create_reminder(message: str, minutes: int = 60) -> dict:
        from miniclaw.tools.reminder import reminder_manager, ReminderType
        from datetime import datetime
        reminder_id = f"reminder_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return reminder_manager.create_reminder(
            reminder_id=reminder_id,
            reminder_type=ReminderType.CUSTOM,
            message=message,
            interval_minutes=minutes,
        )
    
    @staticmethod
    def list_reminders() -> list:
        from miniclaw.tools.reminder import reminder_manager
        return reminder_manager.get_all_reminders()
    
    @staticmethod
    def delete_reminder(reminder_id: str) -> bool:
        from miniclaw.tools.reminder import reminder_manager
        return reminder_manager.delete_reminder(reminder_id)


@skill("pdf", "PDF处理技能，读取和总结PDF文档")
class PDFSkill:
    @staticmethod
    def read_pdf(file_path: str) -> str:
        from miniclaw.rag.pdf_loader import PDFLoader
        loader = PDFLoader()
        chunks = loader.load_pdf(file_path)
        return "\n".join([chunk.content for chunk in chunks])
    
    @staticmethod
    def summarize_pdf(file_path: str) -> str:
        from miniclaw.rag.pdf_loader import PDFLoader
        loader = PDFLoader()
        chunks = loader.load_pdf(file_path)
        
        if not chunks:
            return "PDF文档为空或无法读取"
        
        total_pages = max(chunk.page_number for chunk in chunks)
        total_chunks = len(chunks)
        
        return f"PDF文档摘要:\n- 总页数: {total_pages}\n- 总段落数: {total_chunks}\n- 来源: {chunks[0].source}"
    
    @staticmethod
    def query_pdf(file_path: str, question: str) -> str:
        from miniclaw.rag.pdf_loader import PDFKnowledgeBase
        kb = PDFKnowledgeBase()
        kb.add_pdf(file_path)
        return kb.query_with_context(question)


@skill("summary", "内容总结技能，总结文本和提取关键点")
class SummarySkill:
    @staticmethod
    def summarize_text(text: str, max_length: int = 200) -> str:
        if len(text) <= max_length:
            return text
        
        sentences = text.replace("。", "。\n").split("\n")
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 3:
            return text[:max_length] + "..."
        
        summary = sentences[0]
        for s in sentences[1:]:
            if len(summary) + len(s) < max_length:
                summary += s
            else:
                break
        
        return summary
    
    @staticmethod
    def key_points(text: str) -> list:
        sentences = text.replace("。", "。\n").split("\n")
        sentences = [s.strip() for s in sentences if s.strip()]
        
        keywords = ["重要", "关键", "核心", "主要", "首先", "其次", "最后", "总之", "因此", "所以"]
        
        key_points_list = []
        for s in sentences:
            if any(kw in s for kw in keywords) or len(s) > 50:
                key_points_list.append(s)
        
        return key_points_list[:5]
    
    @staticmethod
    def extract_summary(text: str) -> dict:
        return {
            "original_length": len(text),
            "summary": SummarySkill.summarize_text(text),
            "key_points": SummarySkill.key_points(text),
            "sentence_count": len(text.replace("。", "。\n").split("\n")),
        }


@skill("emotion", "情感分析技能，分析文本情感和生成情感回复")
class EmotionSkill:
    @staticmethod
    def analyze(text: str) -> dict:
        positive_words = ["开心", "高兴", "快乐", "幸福", "满意", "喜欢", "爱", "棒", "好", "优秀"]
        negative_words = ["难过", "伤心", "痛苦", "悲伤", "失望", "讨厌", "恨", "糟糕", "坏", "差"]
        
        positive_count = sum(1 for w in positive_words if w in text)
        negative_count = sum(1 for w in negative_words if w in text)
        
        if positive_count > negative_count:
            sentiment = "positive"
            score = positive_count / (positive_count + negative_count + 1)
        elif negative_count > positive_count:
            sentiment = "negative"
            score = negative_count / (positive_count + negative_count + 1)
        else:
            sentiment = "neutral"
            score = 0.5
        
        return {
            "sentiment": sentiment,
            "score": round(score, 2),
            "positive_count": positive_count,
            "negative_count": negative_count,
        }
    
    @staticmethod
    def get_sentiment(text: str) -> str:
        result = EmotionSkill.analyze(text)
        sentiment_map = {
            "positive": "积极",
            "negative": "消极",
            "neutral": "中性",
        }
        return sentiment_map.get(result["sentiment"], "未知")
    
    @staticmethod
    def emotion_reply(text: str) -> str:
        result = EmotionSkill.analyze(text)
        
        if result["sentiment"] == "positive":
            replies = [
                "看起来你心情不错！继续保持好心情！",
                "很高兴看到你这么开心！",
                "你的积极情绪真有感染力！",
            ]
        elif result["sentiment"] == "negative":
            replies = [
                "看起来你有些不开心，有什么我可以帮助的吗？",
                "抱歉听到这个消息，希望情况会好转。",
                "如果你需要倾诉，我随时在这里。",
            ]
        else:
            replies = [
                "我理解你的感受。",
                "谢谢分享你的想法。",
                "有什么我可以帮助你的吗？",
            ]
        
        return random.choice(replies)


@skill("joke", "笑话娱乐技能，提供笑话、谜语和趣闻")
class JokeSkill:
    _jokes = [
        "为什么程序员总是分不清万圣节和圣诞节？因为 Oct 31 = Dec 25",
        "一个SQL语句走进酒吧，看到两张桌子，问道：我能JOIN你们吗？",
        "为什么Java程序员戴眼镜？因为他们看不见C#",
        "有10种人：懂二进制的和不懂的。",
        "程序员最讨厌什么？1. 写文档 2. 别人不写文档",
    ]
    
    _riddles = [
        {"question": "什么东西越洗越脏？", "answer": "水"},
        {"question": "什么东西有头无脚？", "answer": "砖头"},
        {"question": "什么人一年只工作一天？", "answer": "圣诞老人"},
    ]
    
    _fun_facts = [
        "蜂蜜永远不会变质，考古学家在埃及金字塔中发现的3000年前的蜂蜜仍然可以食用。",
        "章鱼有三颗心脏，两颗用于将血液输送到鳃，一颗用于将血液输送到身体其他部位。",
        "一只蜗牛可以睡三年，如果天气条件不合适的话。",
    ]
    
    @staticmethod
    def get_joke(category: str = "random") -> str:
        return random.choice(JokeSkill._jokes)
    
    @staticmethod
    def get_riddle() -> dict:
        return random.choice(JokeSkill._riddles)
    
    @staticmethod
    def get_fun_fact() -> str:
        return random.choice(JokeSkill._fun_facts)


@skill("calendar", "日历管理技能，管理日程和查询节假日")
class CalendarSkill:
    @staticmethod
    def get_today() -> dict:
        from datetime import datetime
        from miniclaw.utils.helpers import get_weekday_name
        
        now = datetime.now()
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": get_weekday_name(now),
            "year": now.year,
            "month": now.month,
            "day": now.day,
        }
    
    @staticmethod
    def add_event(title: str, date: str, time: str = None) -> dict:
        from datetime import datetime
        from miniclaw.utils.helpers import format_datetime
        
        event_id = f"event_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return {
            "id": event_id,
            "title": title,
            "date": date,
            "time": time,
            "created_at": format_datetime(),
            "status": "pending",
        }
    
    @staticmethod
    def get_holidays(year: int = None) -> list:
        from datetime import datetime
        
        year = year or datetime.now().year
        
        holidays = [
            {"name": "元旦", "date": f"{year}-01-01"},
            {"name": "春节", "date": f"{year}-01-22"},
            {"name": "清明节", "date": f"{year}-04-05"},
            {"name": "劳动节", "date": f"{year}-05-01"},
            {"name": "端午节", "date": f"{year}-06-10"},
            {"name": "中秋节", "date": f"{year}-09-17"},
            {"name": "国庆节", "date": f"{year}-10-01"},
        ]
        
        return holidays
    
    @staticmethod
    def get_date_info(date_str: str) -> dict:
        from datetime import datetime
        from miniclaw.utils.helpers import get_weekday_name
        
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return {
                "date": date_str,
                "weekday": get_weekday_name(dt),
                "year": dt.year,
                "month": dt.month,
                "day": dt.day,
            }
        except ValueError:
            return {"error": "日期格式错误，请使用 YYYY-MM-DD 格式"}
    
    @staticmethod
    def days_until(date_str: str) -> int:
        from datetime import datetime
        
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d")
            now = datetime.now()
            delta = target - now
            return delta.days
        except ValueError:
            return -1
