# MiniClaw

MiniClaw - Personal AI Assistant based on LangGraph and LangChain

## Features

- **Multi-Agent System** - 多智能体协作系统，包含任务、健康、学习、信息查询等专业智能体
- **LangGraph Workflow** - 基于 LangGraph 的智能路由和工作流引擎
- **RAG Support** - 支持向量检索和文档问答
- **Tool Integration** - 内置天气、新闻、提醒、Excel 处理等工具
- **Multiple LLM Providers** - 支持 Ollama、OpenAI、DeepSeek 等多种 LLM 提供商
- **FastAPI Web Interface** - RESTful API 接口
- **Interactive CLI** - 交互式命令行界面
- **Memory & Persistence** - 对话记忆持久化存储

## Architecture

```
miniclaw/
├── agents/          # 智能体实现 (Chat, Task, Health, Learning, Info, Data)
├── core/            # 核心引擎 (Graph, Router, State)
├── rag/             # RAG 系统 (VectorStore, Embeddings, Retriever)
├── tools/           # 工具集 (Weather, News, Reminder, Scheduler, Excel)
├── config/          # 配置管理
├── utils/           # 工具函数
└── web/             # Web 接口
```

## Installation

```bash
# 克隆项目
git clone <repository-url>
cd miniclaw

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .
```

## Configuration

创建 `.env` 文件并配置以下环境变量：

```bash
# LLM 配置 (默认使用 Ollama)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:1.7b

# 可选：OpenAI 配置
# OPENAI_API_KEY=your_openai_key
# OPENAI_MODEL=gpt-4o-mini

# 可选：DeepSeek 配置
# DEEPSEEK_API_KEY=your_deepseek_key
# DEEPSEEK_MODEL=deepseek-chat

# 天气 API（从 weatherapi.com 获取免费 key）
WEATHER_API_KEY=your_weather_api_key

# 数据库配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=miniclaw

# Redis 配置
REDIS_URL=redis://localhost:6379

# 其他配置
DEFAULT_CITY=Beijing
LOG_LEVEL=INFO
```

## Usage

### CLI 命令

```bash
# 查看帮助
miniclaw --help

# 初始化目录
miniclaw init

# 查看配置
miniclaw config

# 测试 LLM 连接
miniclaw test-llm

# 单条消息对话
miniclaw chat "你好"

# 交互式对话
miniclaw interactive

# 启动 Web 服务
miniclaw serve
miniclaw serve --host 0.0.0.0 --port 9190 --reload
```

### Python API

```python
from miniclaw.core.graph import MiniClawApp

app = MiniClawApp()
response = await app.chat(
    message="今天天气怎么样？",
    user_id="user_001",
    session_id="session_001"
)
```

### Web API

启动服务后访问：`http://localhost:9190`

```bash
# 对话接口
curl -X POST "http://localhost:9190/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "user_id": "user_001"}'
```

## Development

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 代码格式化
black src/
ruff check src/

# 运行测试
pytest tests/
```

## Requirements

- Python >= 3.10
- Ollama (本地模型) 或 OpenAI/DeepSeek API Key
- MySQL (可选)
- Redis (可选)

## License

MIT
