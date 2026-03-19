"""
MiniClaw API Tests
Tests for FastAPI endpoints
"""

import pytest
import sys
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import httpx


class TestAPIEndpoints:
    """API端点测试"""
    
    @pytest.fixture
    def test_client(self):
        """创建测试客户端"""
        from miniclaw.api import app
        from httpx import AsyncClient, ASGITransport
        
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, test_client):
        """测试根端点"""
        async with test_client as client:
            response = await client.get("/")
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "MiniClaw API"
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, test_client):
        """测试健康检查端点"""
        async with test_client as client:
            response = await client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_chat_endpoint(self, test_client):
        """测试聊天端点"""
        async with test_client as client:
            response = await client.post(
                "/chat",
                json={
                    "message": "你好",
                    "user_id": "test_user",
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
    
    @pytest.mark.asyncio
    async def test_weather_endpoint(self, test_client):
        """测试天气端点"""
        async with test_client as client:
            response = await client.get("/weather?city=Beijing")
            
            assert response.status_code == 200
            data = response.json()
            assert "weather" in data
    
    @pytest.mark.asyncio
    async def test_news_endpoint(self, test_client):
        """测试新闻端点"""
        async with test_client as client:
            response = await client.get("/news?category=all&count=3")
            
            assert response.status_code == 200
            data = response.json()
            assert "news" in data
    
    @pytest.mark.asyncio
    async def test_reminders_endpoint(self, test_client):
        """测试提醒端点"""
        async with test_client as client:
            response = await client.get("/reminders")
            
            assert response.status_code == 200
            data = response.json()
            assert "reminders" in data
    
    @pytest.mark.asyncio
    async def test_create_reminder_endpoint(self, test_client):
        """测试创建提醒端点"""
        async with test_client as client:
            response = await client.post(
                "/reminders",
                json={
                    "reminder_type": "custom",
                    "message": "测试提醒",
                    "interval_minutes": 60,
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
    
    @pytest.mark.asyncio
    async def test_notifications_endpoint(self, test_client):
        """测试通知端点"""
        async with test_client as client:
            response = await client.get("/notifications")
            
            assert response.status_code == 200
            data = response.json()
            assert "notifications" in data
    
    @pytest.mark.asyncio
    async def test_scheduler_jobs_endpoint(self, test_client):
        """测试调度任务端点"""
        async with test_client as client:
            response = await client.get("/scheduler/jobs")
            
            assert response.status_code == 200
            data = response.json()
            assert "jobs" in data


class TestAPIChatScenarios:
    """API聊天场景测试"""
    
    @pytest.fixture
    def test_client(self):
        """创建测试客户端"""
        from miniclaw.api import app
        from httpx import AsyncClient, ASGITransport
        
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")
    
    @pytest.mark.asyncio
    async def test_chat_learning_scenario(self, test_client):
        """测试学习场景聊天"""
        async with test_client as client:
            response = await client.post(
                "/chat",
                json={
                    "message": "帮我制定一个Python学习计划",
                    "user_id": "test_user",
                }
            )
            
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_chat_task_scenario(self, test_client):
        """测试任务场景聊天"""
        async with test_client as client:
            response = await client.post(
                "/chat",
                json={
                    "message": "创建任务：明天开会",
                    "user_id": "test_user",
                }
            )
            
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_chat_weather_scenario(self, test_client):
        """测试天气场景聊天"""
        async with test_client as client:
            response = await client.post(
                "/chat",
                json={
                    "message": "今天天气怎么样",
                    "user_id": "test_user",
                }
            )
            
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_chat_health_scenario(self, test_client):
        """测试健康场景聊天"""
        async with test_client as client:
            response = await client.post(
                "/chat",
                json={
                    "message": "提醒我休息",
                    "user_id": "test_user",
                }
            )
            
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_chat_data_scenario(self, test_client):
        """测试数据场景聊天"""
        async with test_client as client:
            response = await client.post(
                "/chat",
                json={
                    "message": "新建一个Excel表格",
                    "user_id": "test_user",
                }
            )
            
            assert response.status_code == 200


class TestAPIErrorHandling:
    """API错误处理测试"""
    
    @pytest.fixture
    def test_client(self):
        """创建测试客户端"""
        from miniclaw.api import app
        from httpx import AsyncClient, ASGITransport
        
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")
    
    @pytest.mark.asyncio
    async def test_invalid_endpoint(self, test_client):
        """测试无效端点"""
        async with test_client as client:
            response = await client.get("/invalid_endpoint")
            
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_invalid_chat_request(self, test_client):
        """测试无效聊天请求"""
        async with test_client as client:
            response = await client.post(
                "/chat",
                json={}
            )
            
            assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
