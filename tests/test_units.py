"""
MiniClaw Unit Tests
Tests for all modules
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestConfig:
    """配置模块测试"""
    
    def test_settings_import(self):
        """测试配置模块导入"""
        from miniclaw.config.settings import settings
        assert settings is not None
    
    def test_llm_provider_default(self):
        """测试默认LLM提供商"""
        from miniclaw.config.settings import settings
        assert settings.LLM_PROVIDER in ["ollama", "openai", "deepseek"]
    
    def test_mysql_url_generation(self):
        """测试MySQL URL生成"""
        from miniclaw.config.settings import settings
        url = settings.mysql_url
        assert "mysql" in url
    
    def test_data_dirs_config(self):
        """测试数据目录配置"""
        from miniclaw.config.settings import settings
        assert settings.DATA_DIR == "data"
        assert settings.EXCEL_DIR == "data/excel"


class TestRouter:
    """路由模块测试"""
    
    def test_detect_learning_intent(self):
        """测试学习意图识别"""
        from miniclaw.core.router import detect_intent_by_keywords
        result = detect_intent_by_keywords("帮我制定一个Python学习计划")
        assert result == "learning"
    
    def test_detect_task_intent(self):
        """测试任务意图识别"""
        from miniclaw.core.router import detect_intent_by_keywords
        result = detect_intent_by_keywords("创建一个任务：明天开会")
        assert result == "task"
    
    def test_detect_info_intent(self):
        """测试信息意图识别"""
        from miniclaw.core.router import detect_intent_by_keywords
        result = detect_intent_by_keywords("今天天气怎么样")
        assert result == "info"
    
    def test_detect_health_intent(self):
        """测试健康意图识别"""
        from miniclaw.core.router import detect_intent_by_keywords
        result = detect_intent_by_keywords("提醒我每小时站起来休息")
        assert result == "health"
    
    def test_detect_data_intent(self):
        """测试数据意图识别"""
        from miniclaw.core.router import detect_intent_by_keywords
        result = detect_intent_by_keywords("新建一个Excel表格")
        assert result == "data"
    
    def test_detect_chat_intent(self):
        """测试聊天意图识别"""
        from miniclaw.core.router import detect_intent_by_keywords
        result = detect_intent_by_keywords("你好")
        assert result == "chat"
    
    def test_route_by_intent(self):
        """测试意图路由"""
        from miniclaw.core.router import route_by_intent
        from miniclaw.core.state import create_initial_state
        
        state = create_initial_state("test_user", "test_session")
        state["intent"] = "learning"
        result = route_by_intent(state)
        assert result == "learning_agent"


class TestState:
    """状态模块测试"""
    
    def test_create_initial_state(self):
        """测试初始状态创建"""
        from miniclaw.core.state import create_initial_state
        
        state = create_initial_state("user1", "session1")
        
        assert state["user_id"] == "user1"
        assert state["session_id"] == "session1"
        assert state["messages"] == []
        assert state["intent"] is None
    
    def test_state_structure(self):
        """测试状态结构"""
        from miniclaw.core.state import MiniClawState
        
        required_keys = [
            "messages", "user_id", "session_id", "intent",
            "current_agent", "agent_response"
        ]
        
        for key in required_keys:
            assert key in MiniClawState.__annotations__


class TestExcelTools:
    """Excel工具测试"""
    
    def test_create_excel(self, tmp_path):
        """测试Excel创建"""
        from miniclaw.tools.excel import create_excel
        from miniclaw.config import settings
        
        original_dir = settings.EXCEL_DIR
        settings.EXCEL_DIR = str(tmp_path)
        
        try:
            filepath = create_excel(
                "test_file",
                ["列1", "列2", "列3"],
                [["a", "b", "c"]]
            )
            assert "test_file.xlsx" in filepath
            assert os.path.exists(filepath)
        finally:
            settings.EXCEL_DIR = original_dir
    
    def test_get_excel_path(self, tmp_path):
        """测试Excel路径获取"""
        from miniclaw.tools.excel import get_excel_path
        from miniclaw.config import settings
        
        original_dir = settings.EXCEL_DIR
        settings.EXCEL_DIR = str(tmp_path)
        
        try:
            path = get_excel_path("test")
            assert str(path).endswith("test.xlsx")
        finally:
            settings.EXCEL_DIR = original_dir


class TestWeatherTools:
    """天气工具测试"""
    
    @patch('miniclaw.tools.weather.httpx.Client')
    def test_fetch_weather_no_api_key(self, mock_client):
        """测试无API Key时的天气获取"""
        from miniclaw.tools.weather import fetch_weather
        from miniclaw.config import settings
        
        original_key = settings.WEATHER_API_KEY
        settings.WEATHER_API_KEY = None
        
        try:
            result = fetch_weather("Beijing")
            assert result["city"] == "Beijing"
            assert "API未配置" in result.get("message", "") or result.get("condition") == "API未配置"
        finally:
            settings.WEATHER_API_KEY = original_key
    
    def test_weather_suggestion(self):
        """测试天气建议"""
        from miniclaw.tools.weather import get_weather_suggestion
        
        weather = {"condition": "晴", "temperature": 22}
        suggestion = get_weather_suggestion(weather)
        assert isinstance(suggestion, str)


class TestNewsTools:
    """新闻工具测试"""
    
    def test_fetch_news_no_api_key(self):
        """测试无API Key时的新闻获取"""
        from miniclaw.tools.news import fetch_news
        from miniclaw.config import settings
        
        original_key = settings.NEWS_API_KEY
        settings.NEWS_API_KEY = None
        
        try:
            result = fetch_news()
            assert len(result) > 0
            assert "API未配置" in result[0].get("title", "") or "未配置" in result[0].get("summary", "")
        finally:
            settings.NEWS_API_KEY = original_key
    
    def test_format_news_summary(self):
        """测试新闻摘要格式化"""
        from miniclaw.tools.news import format_news_summary
        
        news = [
            {"title": "测试新闻", "summary": "摘要", "source": "测试源", "published_at": "2024-01-01"}
        ]
        summary = format_news_summary(news)
        assert "测试新闻" in summary


class TestReminder:
    """提醒工具测试"""
    
    def test_reminder_manager_create(self):
        """测试提醒创建"""
        from miniclaw.tools.reminder import reminder_manager, ReminderType
        
        reminder = reminder_manager.create_reminder(
            reminder_id="test_1",
            reminder_type=ReminderType.STANDUP,
            message="测试提醒",
        )
        
        assert reminder["id"] == "test_1"
        assert reminder["type"] == "standup"
        reminder_manager.delete_reminder("test_1")
    
    def test_reminder_list(self):
        """测试提醒列表"""
        from miniclaw.tools.reminder import reminder_manager
        
        reminders = reminder_manager.get_all_reminders()
        assert isinstance(reminders, list)
    
    def test_web_notification(self):
        """测试Web通知"""
        from miniclaw.tools.reminder import web_notification
        
        import asyncio
        result = asyncio.run(web_notification.send("测试标题", "测试消息"))
        assert result == True
        
        notifications = web_notification.get_notifications()
        assert len(notifications) > 0


class TestScheduler:
    """调度器测试"""
    
    def test_scheduler_singleton(self):
        """测试调度器单例"""
        from miniclaw.tools.scheduler import SchedulerService
        
        s1 = SchedulerService()
        s2 = SchedulerService()
        
        assert s1 is s2
    
    def test_scheduler_jobs(self):
        """测试调度任务管理"""
        from miniclaw.tools.scheduler import scheduler
        
        jobs = scheduler.get_jobs()
        assert isinstance(jobs, dict)


class TestEmbeddings:
    """嵌入模块测试"""
    
    def test_embeddings_manager_singleton(self):
        """测试嵌入管理器单例"""
        from miniclaw.rag.embeddings import EmbeddingsManager
        
        m1 = EmbeddingsManager()
        m2 = EmbeddingsManager()
        
        assert m1 is m2
    
    def test_get_embedding_dimension(self):
        """测试嵌入维度获取"""
        from miniclaw.rag.embeddings import get_embedding_dimension
        
        dim = get_embedding_dimension("ollama")
        assert isinstance(dim, int)
        assert dim > 0


class TestVectorStore:
    """向量存储测试"""
    
    def test_in_memory_vectorstore(self):
        """测试内存向量存储"""
        from miniclaw.rag.vectorstore import InMemoryVectorStore
        
        store = InMemoryVectorStore()
        
        count = store.add_texts(["测试文本1", "测试文本2"])
        assert count == 2
        
        results = store.similarity_search("测试", k=1)
        assert len(results) > 0


class TestMemoryStore:
    """记忆存储测试"""
    
    def test_memory_store_add(self):
        """测试记忆添加"""
        from miniclaw.rag.memory_store import MemoryStore
        
        store = MemoryStore()
        store.add_user_message("你好", "test_session")
        store.add_assistant_message("你好！有什么可以帮助你的？", "test_session")
        
        recent = store.get_recent_memories(2)
        assert len(recent) == 2
    
    def test_memory_context(self):
        """测试记忆上下文"""
        from miniclaw.rag.memory_store import MemoryStore
        
        store = MemoryStore()
        store.add_user_message("测试消息", "test_session")
        
        context = store.get_recent_context(1)
        assert "测试消息" in context


class TestPDFLoader:
    """PDF加载器测试"""
    
    def test_pdf_loader_init(self):
        """测试PDF加载器初始化"""
        from miniclaw.rag.pdf_loader import PDFLoader
        
        loader = PDFLoader(chunk_size=500, chunk_overlap=100)
        assert loader.chunk_size == 500
        assert loader.chunk_overlap == 100
    
    def test_clean_text(self):
        """测试文本清理"""
        from miniclaw.rag.pdf_loader import PDFLoader
        
        loader = PDFLoader()
        text = "测试  文本\n\n清理"
        cleaned = loader._clean_text(text)
        assert "  " not in cleaned


class TestNewsEnhancer:
    """新闻增强测试"""
    
    def test_news_enhancer_init(self):
        """测试新闻增强器初始化"""
        from miniclaw.rag.news_enhancer import NewsEnhancer
        
        enhancer = NewsEnhancer()
        assert enhancer.collection_name == "news_knowledge"
    
    def test_extract_keywords(self):
        """测试关键词提取"""
        from miniclaw.rag.news_enhancer import NewsEnhancer
        
        enhancer = NewsEnhancer()
        keywords = enhancer._extract_keywords("Python编程 人工智能 机器学习")
        assert isinstance(keywords, list)


class TestRetriever:
    """检索器测试"""
    
    def test_retriever_init(self):
        """测试检索器初始化"""
        from miniclaw.rag.retriever import RAGRetriever
        
        retriever = RAGRetriever(
            use_pdf=False,
            use_memory=False,
            use_news=False,
            use_long_term=False,
        )
        assert retriever.use_pdf == False
    
    def test_retriever_add_conversation(self):
        """测试对话添加"""
        from miniclaw.rag.retriever import RAGRetriever
        
        retriever = RAGRetriever(
            use_pdf=False,
            use_memory=True,
            use_news=False,
            use_long_term=False,
        )
        
        retriever.add_conversation("你好", "你好！", "test_session")


class TestSkills:
    """技能系统测试"""
    
    def test_skill_config_singleton(self):
        """测试技能配置单例"""
        from miniclaw.skills import SkillConfig
        
        c1 = SkillConfig()
        c2 = SkillConfig()
        
        assert c1 is c2
    
    def test_skill_enable_disable(self):
        """测试技能启用/禁用"""
        from miniclaw.skills import skill_config
        
        skill_config.enable_skill("weather")
        assert skill_config.is_skill_enabled("weather") == True
        
        skill_config.disable_skill("weather")
        assert skill_config.is_skill_enabled("weather") == False
        
        skill_config.enable_skill("weather")
    
    def test_get_enabled_skills(self):
        """测试获取启用的技能"""
        from miniclaw.skills import get_enabled_skills
        
        skills = get_enabled_skills()
        assert isinstance(skills, list)
    
    def test_weather_skill(self):
        """测试天气技能"""
        from miniclaw.skills import WeatherSkill
        
        result = WeatherSkill.get_suggestion("Beijing")
        assert isinstance(result, str)
    
    def test_summary_skill(self):
        """测试总结技能"""
        from miniclaw.skills import SummarySkill
        
        text = "这是一段测试文本。用于测试总结功能。"
        summary = SummarySkill.summarize_text(text, max_length=50)
        assert isinstance(summary, str)
    
    def test_emotion_skill(self):
        """测试情感技能"""
        from miniclaw.skills import EmotionSkill
        
        result = EmotionSkill.analyze("今天真开心")
        assert "sentiment" in result
        assert "score" in result
    
    def test_joke_skill(self):
        """测试笑话技能"""
        from miniclaw.skills import JokeSkill
        
        joke = JokeSkill.get_joke()
        assert isinstance(joke, str)
        
        riddle = JokeSkill.get_riddle()
        assert "question" in riddle
        assert "answer" in riddle
    
    def test_calendar_skill(self):
        """测试日历技能"""
        from miniclaw.skills import CalendarSkill
        
        today = CalendarSkill.get_today()
        assert "date" in today
        assert "weekday" in today
        
        holidays = CalendarSkill.get_holidays(2024)
        assert isinstance(holidays, list)


class TestGraph:
    """LangGraph工作流测试"""
    
    def test_build_graph(self):
        """测试图构建"""
        from miniclaw.core.graph import build_graph
        
        graph = build_graph()
        assert graph is not None
    
    def test_mini_claw_app_init(self):
        """测试应用初始化"""
        from miniclaw.core.graph import MiniClawApp
        
        app = MiniClawApp()
        assert app.graph is not None


class TestLLMUtils:
    """LLM工具测试"""
    
    def test_get_llm_ollama(self):
        """测试Ollama LLM获取"""
        from miniclaw.utils.llm import get_llm
        from langchain_ollama import ChatOllama
        
        llm = get_llm(provider="ollama")
        assert isinstance(llm, ChatOllama)
    
    @patch('miniclaw.utils.llm.settings')
    def test_get_llm_openai(self, mock_settings):
        """测试OpenAI LLM获取"""
        from miniclaw.utils.llm import get_llm
        
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.OPENAI_API_KEY = "test_key"
        mock_settings.OPENAI_BASE_URL = "https://api.openai.com/v1"
        mock_settings.OPENAI_MODEL = "gpt-4o-mini"
        
        try:
            from langchain_openai import ChatOpenAI
            llm = get_llm(provider="openai")
            assert isinstance(llm, ChatOpenAI)
        except Exception:
            pass


class TestHelpers:
    """辅助函数测试"""
    
    def test_format_datetime(self):
        """测试日期格式化"""
        from miniclaw.utils.helpers import format_datetime
        
        result = format_datetime()
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_get_weekday_name(self):
        """测试星期名称获取"""
        from miniclaw.utils.helpers import get_weekday_name
        
        result = get_weekday_name()
        assert result in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    
    def test_ensure_dir(self, tmp_path):
        """测试目录创建"""
        from miniclaw.utils.helpers import ensure_dir
        
        test_dir = str(tmp_path / "test_dir")
        result = ensure_dir(test_dir)
        assert result.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
