"""
MiniClaw Settings Configuration
Supports multiple LLM providers: Ollama (default), OpenAI, DeepSeek
"""

from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    LLM_PROVIDER: Literal["ollama", "openai", "deepseek"] = Field(
        default="ollama",
        description="LLM provider to use",
    )

    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL",
    )
    OLLAMA_MODEL: str = Field(
        default="llama3",
        description="Ollama model name",
    )

    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key",
    )
    OPENAI_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL",
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model name",
    )

    DEEPSEEK_API_KEY: Optional[str] = Field(
        default=None,
        description="DeepSeek API key",
    )
    DEEPSEEK_BASE_URL: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API base URL",
    )
    DEEPSEEK_MODEL: str = Field(
        default="deepseek-chat",
        description="DeepSeek model name",
    )

    MYSQL_HOST: str = Field(default="localhost")
    MYSQL_PORT: int = Field(default=3306)
    MYSQL_USER: str = Field(default="root")
    MYSQL_PASSWORD: str = Field(default="")
    MYSQL_DATABASE: str = Field(default="miniclaw")

    REDIS_URL: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )

    WEATHER_API_KEY: Optional[str] = Field(default=None)
    WEATHER_API_URL: str = Field(
        default="https://api.weatherapi.com/v1",
    )

    NEWS_API_KEY: Optional[str] = Field(default=None)

    DEFAULT_CITY: str = Field(default="Beijing")
    MORNING_GREETING_TIME: str = Field(default="08:00")
    NOON_REMINDER_TIME: str = Field(default="12:00")
    NIGHT_REMINDER_TIME: str = Field(default="22:00")
    STANDUP_INTERVAL_MINUTES: int = Field(default=60)

    LOG_LEVEL: str = Field(default="INFO")

    DATA_DIR: str = Field(default="data")
    EXCEL_DIR: str = Field(default="data/excel")
    KNOWLEDGE_DIR: str = Field(default="data/knowledge")
    LOGS_DIR: str = Field(default="data/logs")

    MILVUS_HOST: str = Field(
        default="localhost",
        description="Milvus server host",
    )
    MILVUS_PORT: int = Field(
        default=19530,
        description="Milvus server port",
    )
    MILVUS_COLLECTION: str = Field(
        default="miniclaw",
        description="Default Milvus collection name",
    )
    EMBEDDING_PROVIDER: str = Field(
        default="ollama",
        description="Embedding provider: openai, ollama, huggingface",
    )
    EMBEDDING_MODEL: str = Field(
        default="nomic-embed-text",
        description="Embedding model name",
    )

    SKILLS_DIR: str = Field(
        default="skills",
        description="Skills directory",
    )
    ENABLED_SKILLS: str = Field(
        default="weather,news,reminder,pdf,summary,emotion,joke,calendar",
        description="Comma-separated list of enabled skills",
    )
    MCP_CONFIG_PATH: str = Field(
        default="mcp_config.yaml",
        description="MCP configuration file path",
    )

    @property
    def mysql_url(self) -> str:
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def mysql_url_sync(self) -> str:
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"


settings = Settings()
