from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


def _resolve_env_file():
    this_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(this_dir, "..", ".env"),
        os.path.join(this_dir, "..", "..", "src", ".env"),
        os.path.join(os.getcwd(), "src", ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for p in candidates:
        p = os.path.normpath(p)
        if os.path.isfile(p):
            return p
    return ".env"


class Settings(BaseSettings):
    LLM_PROVIDER: str = Field(default="openai", description="LLM provider: openai/ollama/deepseek")
    LLM_API_KEY: Optional[str] = Field(default=None)
    LLM_BASE_URL: Optional[str] = Field(default=None)
    LLM_MODEL: str = Field(default="gpt-4o")
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_BASE_URL: Optional[str] = Field(default=None)
    OPENAI_MODEL: str = Field(default="gpt-4o")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="llama3")
    DEEPSEEK_API_KEY: Optional[str] = Field(default=None)
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com/v1")
    DEEPSEEK_MODEL: str = Field(default="deepseek-chat")
    TAVILY_API_KEY: Optional[str] = Field(default=None)
    DEFAULT_CONTEXT_TOKENS: int = Field(default=128000)
    MAX_LOOP_ITERATIONS: int = Field(default=25)
    MAX_TOOL_CALLS: int = Field(default=50)

    MEMORY_EMBEDDING_PROVIDER: str = Field(default="auto", description="Embedding provider: auto/openai/local/none")
    MEMORY_EMBEDDING_MODEL: Optional[str] = Field(default=None)
    MEMORY_VECTOR_WEIGHT: float = Field(default=0.7)
    MEMORY_TEXT_WEIGHT: float = Field(default=0.3)
    MEMORY_TEMPORAL_DECAY_ENABLED: bool = Field(default=False)
    MEMORY_TEMPORAL_DECAY_HALF_LIFE_DAYS: float = Field(default=30.0)
    MEMORY_MMR_ENABLED: bool = Field(default=False)
    MEMORY_MMR_LAMBDA: float = Field(default=0.7)
    MEMORY_FLUSH_SOFT_THRESHOLD_TOKENS: int = Field(default=4000)
    MEMORY_FLUSH_RESERVE_TOKENS_FLOOR: int = Field(default=20000)

    SKILLS_WATCH_ENABLED: bool = Field(default=True)
    SKILLS_WATCH_DEBOUNCE_MS: int = Field(default=250)
    SKILLS_PROMPT_MAX_CHARS: int = Field(default=8000)

    SESSION_RESET_MODE: str = Field(default="daily", description="Session reset mode: daily/idle")
    SESSION_RESET_AT_HOUR: int = Field(default=4)
    SESSION_IDLE_MINUTES_DM: int = Field(default=1440)
    SESSION_IDLE_MINUTES_GROUP: int = Field(default=240)
    SESSION_PRUNE_MAX_AGE_HOURS: int = Field(default=24)

    @property
    def effective_api_key(self) -> Optional[str]:
        return self.LLM_API_KEY or self.OPENAI_API_KEY

    @property
    def effective_base_url(self) -> Optional[str]:
        return self.LLM_BASE_URL or self.OPENAI_BASE_URL

    @property
    def effective_model(self) -> str:
        return self.LLM_MODEL if self.LLM_MODEL != "gpt-4o" or not self.OPENAI_MODEL else self.OPENAI_MODEL

    class Config:
        env_file = _resolve_env_file()
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
