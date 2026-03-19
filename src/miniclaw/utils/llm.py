"""
MiniClaw LLM Utilities
Supports multiple LLM providers: Ollama (default), OpenAI, DeepSeek
"""

from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from miniclaw.config.settings import settings


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    **kwargs,
) -> BaseChatModel:
    provider = provider or settings.LLM_PROVIDER
    
    if provider == "ollama":
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=model or settings.OLLAMA_MODEL,
            temperature=temperature,
            **kwargs,
        )
    
    elif provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=model or settings.OPENAI_MODEL,
            temperature=temperature,
            **kwargs,
        )
    
    elif provider == "deepseek":
        if not settings.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY is required for DeepSeek provider")
        return ChatOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=model or settings.DEEPSEEK_MODEL,
            temperature=temperature,
            **kwargs,
        )
    
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def get_fast_llm(**kwargs) -> BaseChatModel:
    return get_llm(temperature=0.3, **kwargs)


def get_smart_llm(**kwargs) -> BaseChatModel:
    return get_llm(temperature=0.7, **kwargs)
