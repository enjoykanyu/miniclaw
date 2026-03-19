"""
MiniClaw Integration Tests
Tests for LangGraph workflow and Agent collaboration
"""

import pytest
import sys
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestLangGraphWorkflow:
    """LangGraph工作流集成测试"""
    
    def test_graph_build(self):
        """测试图构建"""
        from miniclaw.core.graph import build_graph
        
        graph = build_graph()
        assert graph is not None
    
    def test_graph_nodes_exist(self):
        """测试图节点存在"""
        from miniclaw.core.graph import build_graph
        
        graph = build_graph()
        
        expected_nodes = [
            "intent_router",
            "learning_agent",
            "task_agent",
            "info_agent",
            "health_agent",
            "data_agent",
            "chat_agent",
            "response",
        ]
        
        for node in expected_nodes:
            assert node in graph.nodes
    
    def test_mini_claw_app_creation(self):
        """测试应用创建"""
        from miniclaw.core.graph import MiniClawApp
        
        app = MiniClawApp()
        assert app.graph is not None
    
    @pytest.mark.asyncio
    async def test_chat_basic(self):
        """测试基本对话"""
        from miniclaw.core.graph import MiniClawApp
        
        app = MiniClawApp()
        
        response = await app.chat(
            message="你好",
            user_id="test_user",
            session_id="test_session",
        )
        
        assert response is not None
        assert isinstance(response, str)
    
    @pytest.mark.asyncio
    async def test_chat_learning_intent(self):
        """测试学习意图对话"""
        from miniclaw.core.graph import MiniClawApp
        
        app = MiniClawApp()
        
        response = await app.chat(
            message="帮我制定一个Python学习计划",
            user_id="test_user",
            session_id="test_session",
        )
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_chat_task_intent(self):
        """测试任务意图对话"""
        from miniclaw.core.graph import MiniClawApp
        
        app = MiniClawApp()
        
        response = await app.chat(
            message="创建一个任务：明天开会",
            user_id="test_user",
            session_id="test_session",
        )
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_chat_info_intent(self):
        """测试信息意图对话"""
        from miniclaw.core.graph import MiniClawApp
        
        app = MiniClawApp()
        
        response = await app.chat(
            message="今天天气怎么样",
            user_id="test_user",
            session_id="test_session",
        )
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_chat_health_intent(self):
        """测试健康意图对话"""
        from miniclaw.core.graph import MiniClawApp
        
        app = MiniClawApp()
        
        response = await app.chat(
            message="提醒我休息",
            user_id="test_user",
            session_id="test_session",
        )
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_chat_data_intent(self):
        """测试数据意图对话"""
        from miniclaw.core.graph import MiniClawApp
        
        app = MiniClawApp()
        
        response = await app.chat(
            message="新建一个Excel表格",
            user_id="test_user",
            session_id="test_session",
        )
        
        assert response is not None


class TestAgentCollaboration:
    """Agent协作测试"""
    
    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self):
        """测试多轮对话"""
        from miniclaw.core.graph import MiniClawApp
        
        app = MiniClawApp()
        
        response1 = await app.chat(
            message="你好",
            user_id="test_user",
            session_id="multi_turn_session",
            thread_id="multi_turn_thread",
        )
        
        response2 = await app.chat(
            message="帮我创建一个任务",
            user_id="test_user",
            session_id="multi_turn_session",
            thread_id="multi_turn_thread",
        )
        
        assert response1 is not None
        assert response2 is not None
    
    def test_state_persistence(self):
        """测试状态持久化"""
        from miniclaw.core.state import create_initial_state
        from miniclaw.core.graph import MiniClawApp
        
        app = MiniClawApp()
        
        initial_state = create_initial_state("test_user", "test_session")
        
        assert initial_state["user_id"] == "test_user"
        assert initial_state["session_id"] == "test_session"


class TestRouterIntegration:
    """路由集成测试"""
    
    @pytest.mark.asyncio
    async def test_intent_detection_integration(self):
        """测试意图检测集成"""
        from miniclaw.core.router import detect_intent_with_llm
        
        result = await detect_intent_with_llm("帮我制定学习计划")
        
        assert result.intent in ["learning", "task", "info", "health", "data", "chat"]
        assert 0 <= result.confidence <= 1


class TestToolsIntegration:
    """工具集成测试"""
    
    def test_excel_workflow(self, tmp_path):
        """测试Excel工作流"""
        from miniclaw.tools.excel import create_excel, read_excel, update_cell
        from miniclaw.config import settings
        
        settings.EXCEL_DIR = str(tmp_path)
        
        filepath = create_excel(
            "integration_test",
            ["任务", "状态", "优先级"],
            [["任务1", "待完成", "高"]],
        )
        
        assert os.path.exists(filepath)
        
        df = read_excel("integration_test")
        assert len(df) == 1
        
        update_cell("integration_test", 2, "状态", "已完成")
        
        df_updated = read_excel("integration_test")
        assert df_updated.iloc[0]["状态"] == "已完成"
    
    def test_reminder_workflow(self):
        """测试提醒工作流"""
        from miniclaw.tools.reminder import reminder_manager, ReminderType
        
        reminder = reminder_manager.create_reminder(
            reminder_id="integration_test",
            reminder_type=ReminderType.CUSTOM,
            message="集成测试提醒",
        )
        
        assert reminder["id"] == "integration_test"
        
        reminders = reminder_manager.get_all_reminders()
        found = any(r["id"] == "integration_test" for r in reminders)
        assert found
        
        reminder_manager.delete_reminder("integration_test")
    
    def test_scheduler_workflow(self):
        """测试调度器工作流"""
        from miniclaw.tools.scheduler import scheduler
        
        def dummy_callback():
            pass
        
        job_id = scheduler.add_interval_job(
            "test_job",
            dummy_callback,
            minutes=30,
        )
        
        assert job_id == "test_job"
        
        jobs = scheduler.get_jobs()
        assert "test_job" in jobs
        
        scheduler.remove_job("test_job")


class TestRAGIntegration:
    """RAG集成测试"""
    
    def test_memory_store_workflow(self):
        """测试记忆存储工作流"""
        from miniclaw.rag.memory_store import MemoryStore
        
        store = MemoryStore()
        
        store.add_user_message("什么是Python？", "test_session")
        store.add_assistant_message("Python是一种编程语言。", "test_session")
        
        context = store.get_recent_context(2)
        assert "Python" in context
    
    def test_in_memory_vectorstore_workflow(self):
        """测试内存向量存储工作流"""
        from miniclaw.rag.vectorstore import InMemoryVectorStore
        
        store = InMemoryVectorStore()
        
        store.add_texts(
            ["Python是一种编程语言", "Java也是一种编程语言", "今天天气很好"],
            metadatas=[
                {"topic": "programming"},
                {"topic": "programming"},
                {"topic": "weather"},
            ]
        )
        
        results = store.similarity_search("编程语言", k=2)
        assert len(results) == 2


class TestSkillIntegration:
    """技能集成测试"""
    
    def test_skill_registry(self):
        """测试技能注册"""
        from miniclaw.skills import skill_registry
        
        skills = skill_registry.list_skills()
        assert isinstance(skills, list)
    
    def test_skill_execution(self):
        """测试技能执行"""
        from miniclaw.skills import skill_registry
        
        weather_skill = skill_registry.get("weather")
        if weather_skill:
            assert "get_weather" in weather_skill.functions
    
    def test_skill_config_workflow(self):
        """测试技能配置工作流"""
        from miniclaw.skills import skill_config
        
        original_state = skill_config.is_skill_enabled("joke")
        
        skill_config.disable_skill("joke")
        assert skill_config.is_skill_enabled("joke") == False
        
        skill_config.enable_skill("joke")
        assert skill_config.is_skill_enabled("joke") == True
        
        if not original_state:
            skill_config.disable_skill("joke")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
