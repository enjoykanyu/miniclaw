"""
MiniClaw Web Frontend
Simple web interface for task notifications and interactions
"""

import asyncio
from datetime import datetime
from typing import Optional

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

from miniclaw.core.graph import MiniClawApp
from miniclaw.utils.helpers import init_data_dirs, format_datetime, get_weekday_name
from miniclaw.tools.reminder import web_notification, reminder_manager
from miniclaw.tools.weather import fetch_weather, get_weather_suggestion
from miniclaw.tools.news import fetch_news, format_news_summary
from miniclaw.config.settings import settings


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "user_id" not in st.session_state:
        st.session_state.user_id = "web_user"
    if "miniclaw_app" not in st.session_state:
        st.session_state.miniclaw_app = MiniClawApp()


def render_sidebar():
    with st.sidebar:
        st.title("⚙️ 设置")
        
        st.session_state.user_id = st.text_input(
            "用户ID",
            value=st.session_state.user_id,
        )
        
        st.divider()
        
        st.subheader("📍 位置设置")
        city = st.text_input("默认城市", value=settings.DEFAULT_CITY)
        
        if st.button("🌤️ 获取天气"):
            weather = fetch_weather(city)
            st.json(weather)
        
        st.divider()
        
        st.subheader("⏰ 提醒设置")
        standup_interval = st.slider(
            "休息提醒间隔（分钟）",
            min_value=15,
            max_value=120,
            value=settings.STANDUP_INTERVAL_MINUTES,
        )
        
        st.divider()
        
        st.subheader("📊 系统状态")
        st.info(f"LLM Provider: {settings.LLM_PROVIDER}")
        st.info(f"Model: {getattr(settings, f'{settings.LLM_PROVIDER.upper()}_MODEL', 'N/A')}")


def render_chat():
    st.subheader("💬 对话")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if prompt := st.chat_input("输入消息..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                response = asyncio.run(
                    st.session_state.miniclaw_app.chat(
                        message=prompt,
                        user_id=st.session_state.user_id,
                    )
                )
            st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})


def render_notifications():
    st.subheader("🔔 通知中心")
    
    notifications = web_notification.get_notifications()
    
    if not notifications:
        st.info("暂无通知")
        return
    
    for notif in notifications:
        with st.container():
            col1, col2 = st.columns([4, 1])
            
            with col1:
                status = "🟢" if notif.get("read") else "🔴"
                st.markdown(f"**{status} {notif.get('title', '通知')}**")
                st.markdown(notif.get("message", ""))
                st.caption(notif.get("created_at", ""))
            
            with col2:
                if not notif.get("read"):
                    if st.button("标记已读", key=notif.get("id")):
                        web_notification.mark_read(notif.get("id"))
                        st.rerun()
            
            st.divider()


def render_tasks():
    st.subheader("📋 任务列表")
    
    reminders = reminder_manager.get_all_reminders()
    
    if not reminders:
        st.info("暂无任务提醒")
        return
    
    for reminder in reminders:
        with st.expander(f"📌 {reminder.get('type', '任务')} - {reminder.get('message', '')[:30]}..."):
            st.json(reminder)


def render_dashboard():
    st.subheader("📊 今日概览")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        weather = fetch_weather(settings.DEFAULT_CITY)
        st.metric(
            label="🌡️ 当前温度",
            value=f"{weather.get('temperature', 'N/A')}°C",
            delta=weather.get('condition', 'N/A'),
        )
    
    with col2:
        notifications = web_notification.get_notifications(unread_only=True)
        st.metric(
            label="🔔 未读通知",
            value=len(notifications),
        )
    
    with col3:
        reminders = reminder_manager.get_all_reminders()
        st.metric(
            label="⏰ 活跃提醒",
            value=len(reminders),
        )


def main():
    st.set_page_config(
        page_title="MiniClaw - 个人智能助手",
        page_icon="🤖",
        layout="wide",
    )
    
    init_data_dirs()
    init_session_state()
    
    st.title("🤖 MiniClaw 个人智能助手")
    st.caption(f"{format_datetime()} | {get_weekday_name()}")
    
    render_sidebar()
    
    tab1, tab2, tab3, tab4 = st.tabs(["💬 对话", "📊 概览", "🔔 通知", "📋 任务"])
    
    with tab1:
        render_chat()
    
    with tab2:
        render_dashboard()
    
    with tab3:
        render_notifications()
    
    with tab4:
        render_tasks()


if __name__ == "__main__":
    main()
