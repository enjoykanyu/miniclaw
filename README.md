# MiniClaw

MiniClaw - 企业级多智能体 AI 助手平台，基于 LangGraph 多代理架构和 LangChain 生态构建，支持深度思考、联网搜索、知识库 RAG、MCP 协议扩展、Skill技能等高级能力。

**中文** | [English](README_EN.md) | [日本語](README_JP.md) | [한국어](README_KR.md)

## 核心特性

### 多智能体协作系统

- **Supervisor-Worker 架构** - 基于 LangGraph 的监督者-执行者模式，Supervisor 负责任务路由，Worker 负责专业领域执行
- **6 大专业 Agent** - Chat(对话)、Task(任务)、Info(信息查询)、Learning(学习)、Health(健康)、Data(数据分析)
- **动态工具注入** - 支持 Skill 条件注入和强制工具注入（深度思考、联网搜索）

### 知识库与 RAG

- **企业级知识库管理** - 支持创建、配置、删除知识库，可指定嵌入模型、重排序模型、分块策略
- **混合检索引擎** - Dense 向量检索 + BM25 关键词检索 + RRF 融合算法
- **多向量存储后端** - FAISS（本地）和 Milvus（生产级）
- **多格式文档支持** - PDF、Markdown、TXT、Word 等格式解析与向量化
- **意图识别/强制检索** - 支持自动判断或强制使用知识库检索

### 工具与扩展

- **MCP 协议支持** - Model Context Protocol，连接外部工具和服务
- **Skill 技能系统** - 基于 SKILL.md 声明式配置，条件化工具注入
- **强制联网搜索** - Tavily API / DuckDuckGo 双后端，程序化预执行搜索
- **深度思考模式** - 强制调用 think 工具进行结构化推理
- **内置工具集** - 天气查询、新闻获取、提醒管理、Excel 处理等

### 前端交互

- **Next.js 14 + React** - 现代化前端架构
- **流式响应** - SSE 实时输出，支持思考过程可视化
- **知识库管理 UI** - 拖拽上传、配置管理、检索模式切换
- **多会话管理** - 会话创建、重命名、历史记录

## 业务架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户交互层                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  聊天界面    │  │ 知识库管理  │  │  会话管理   │  │   Agent 设置面板    │ │
│  │ ChatPanel   │  │  KB Panel   │  │  Session    │  │   Settings Panel    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         └─────────────────┴─────────────────┴────────────────────┘            │
│                                    │                                         │
│                              HTTP / SSE                                      │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼─────────────────────────────────────────┐
│                              API 网关层                                       │
│                                    │                                         │
│  ┌─────────────────────────────────┴─────────────────────────────────────┐   │
│  │                    FastAPI RESTful API                                  │   │
│  │  /chat/stream  /chat  /knowledge-bases  /sessions  /tools  /mcp       │   │
│  └─────────────────────────────────┬─────────────────────────────────────┘   │
│                                    │                                         │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼─────────────────────────────────────────┐
│                           LangGraph 工作流引擎                                │
│                                    │                                         │
│  ┌─────────────────────────────────┴─────────────────────────────────────┐   │
│  │                         Supervisor 路由节点                             │   │
│  │  输入: 用户消息 + metadata(force_think, force_search, selected_kbs)   │   │
│  │  输出: Command(goto=WorkerType)                                        │   │
│  └─────────────┬─────────────┬─────────────┬─────────────┬───────────────┘   │
│                │             │             │             │                  │
│         ┌──────┘      ┌──────┘      ┌──────┘      ┌──────┘                  │
│         ▼             ▼             ▼             ▼                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │
│  │  Chat    │  │  Info    │  │  Task    │  │ Learning │  ...                │
│  │  Agent   │  │  Agent   │  │  Agent   │  │  Agent   │                     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                     │
│       │             │             │             │                            │
│       └─────────────┴─────────────┴─────────────┘                            │
│                     │                                                        │
│              ┌──────┴──────┐                                                 │
│              ▼             ▼                                                 │
│  ┌─────────────────┐  ┌─────────────────┐                                    │
│  │   RAG Node      │  │   Tool Call     │                                    │
│  │ (知识库检索)     │  │ (工具执行)       │                                    │
│  └─────────────────┘  └─────────────────┘                                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼─────────────────────────────────────────┐
│                              能力扩展层                                       │
│                                    │                                         │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐   │
│  │         Skill 技能系统            │         MCP 协议扩展                 │   │
│  │  ┌─────────────────────────┐    │    ┌─────────────────────────┐     │   │
│  │  │  SKILL.md 声明式配置     │    │    │  MCP Server 连接管理     │     │   │
│  │  │  - agent 绑定            │    │    │  - STDIO / SSE 传输      │     │   │
│  │  │  - tools 条件注入        │    │    │  - 工具发现与调用          │     │   │
│  │  │  - condition 触发条件    │    │    │  - OAuth 认证            │     │   │
│  │  └─────────────────────────┘    │    └─────────────────────────┘     │   │
│  └─────────────────────────────────┴─────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼─────────────────────────────────────────┐
│                              基础设施层                                       │
│                                    │                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Embedding  │  │  VectorStore│  │    LLM      │  │   Memory/Persistence│ │
│  │  (Ollama/   │  │  (FAISS/    │  │ (Ollama/    │  │   (MemorySaver/     │ │
│  │   OpenAI/   │  │   Milvus)   │  │  OpenAI/    │  │    FileSystem)      │ │
│  │   HF)       │  │             │  │  DeepSeek)  │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 技术架构

### 后端架构

```
src/miniclaw/
├── agents/                    # 多智能体系统
│   ├── supervisor.py          # Supervisor Agent - 任务路由与分发
│   ├── worker.py              # BaseWorker - Worker 基类，工具注入与执行
│   ├── chat.py                # Chat Agent - 通用对话
│   ├── info.py                # Info Agent - 信息查询（天气、新闻、RAG）
│   ├── task.py                # Task Agent - 任务管理
│   ├── learning.py            # Learning Agent - 学习辅助
│   ├── health.py              # Health Agent - 健康咨询
│   ├── data.py                # Data Agent - 数据分析
│   └── base.py                # Agent 基类定义
│
├── core/                      # 核心引擎
│   ├── graph.py               # LangGraph 工作流定义（MiniClawApp）
│   ├── state.py               # 状态定义（MiniClawState）
│   ├── router.py              # 路由逻辑
│   ├── error_handler.py       # 错误处理与重试
│   └── exceptions.py          # 异常定义
│
├── rag/                       # RAG 检索增强系统
│   ├── service.py             # RAGService - 知识库管理与检索入口
│   ├── vectorstore.py         # FAISS/Milvus 向量存储实现
│   ├── embeddings.py          # Embedding 服务（Ollama/OpenAI/HF）
│   ├── retriever.py           # HybridRetriever - 混合检索（Dense+BM25+RRF）
│   ├── rag_node.py            # LangGraph RAG 节点（detect/retrieve/generate）
│   ├── rag_tools.py           # RAG 工具（rag_search 等）
│   ├── document_loader.py     # 文档加载与解析
│   ├── chunking.py            # 文档分块策略
│   └── knowledge_manager.py   # 知识库管理
│
├── skills/                    # Skill 技能系统
│   ├── registry.py            # SkillRegistry - 全局单例注册表
│   ├── loader.py              # SkillLoader - SKILL.md 解析器
│   └── builtin/               # 内置 Skills
│       └── web_search/        # 联网搜索 Skill
│           └── SKILL.md       # 声明式配置（agent/tools/condition）
│
├── mcp/                       # MCP 协议实现
│   ├── manager.py             # MCP 连接管理
│   ├── client.py              # MCP 客户端
│   ├── tools.py               # MCP 工具注册与发现
│   └── protocol.py            # MCP 协议定义
│
├── tools/                     # 工具集
│   ├── tavily.py              # Tavily 联网搜索
│   ├── think.py               # 深度思考工具
│   ├── weather.py             # 天气查询
│   ├── news.py                # 新闻获取
│   ├── reminder.py            # 提醒管理
│   ├── scheduler.py           # 定时任务
│   ├── excel.py               # Excel 处理
│   └── builtin/               # 内置工具
│
├── memory/                    # 记忆系统
│   ├── short_term.py          # 短期记忆
│   ├── mid_term.py            # 中期记忆
│   ├── long_term.py           # 长期记忆
│   └── checkpointer.py        # 状态检查点
│
├── config/                    # 配置管理
│   ├── settings.py            # 全局配置（Pydantic Settings）
│   └── prompts/               # 提示词模板
│
└── api.py                     # FastAPI 主入口
```

### 前端架构

```
frontend/src/
├── app/                       # Next.js App Router
│   ├── page.tsx               # 主页面
│   └── layout.tsx             # 根布局
│
├── components/
│   ├── chat/                  # 聊天组件
│   │   ├── ChatPanel.tsx      # 聊天面板主组件
│   │   ├── ChatInput.tsx      # 输入框（工具开关、KB 选择）
│   │   ├── ChatMessage.tsx    # 消息渲染
│   │   ├── ThoughtChain.tsx   # 思考过程可视化
│   │   └── RetrievalCard.tsx  # 检索结果卡片
│   │
│   ├── knowledge/             # 知识库管理
│   │   ├── KnowledgeBasePanel.tsx   # 知识库网格列表
│   │   ├── KbCreateModal.tsx        # 创建知识库弹窗
│   │   └── KbDetailPanel.tsx        # 知识库详情（上传/管理）
│   │
│   ├── layout/                # 布局组件
│   │   ├── Navbar.tsx         # 顶部导航
│   │   ├── Sidebar.tsx        # 侧边栏
│   │   └── ResizeHandle.tsx   # 拖拽调整大小
│   │
│   └── editor/                # 编辑器组件
│       └── InspectorPanel.tsx # 检查面板
│
└── lib/
    ├── api.ts                 # API 客户端（streamChat 等）
    └── store.tsx              # React Context 全局状态管理
```

## 核心流程

### 1. 强制联网搜索流程

```
用户点击"联网搜索"按钮
        │
        ▼
前端: forceSearch=true ─────────────────────────────┐
        │                                           │
        ▼                                           │
后端 stream():                                       │
  metadata.force_search=true                         │
        │                                           │
        ▼                                           │
_worker._get_force_tools()                           │
  → Skill 条件注入: web_search Skill                 │
    → condition=force_search 匹配                    │
    → _load_tool_by_name("tavily")                   │
  → 兜底注入: tavily 工具                            │
        │                                           │
        ▼                                           │
_execute_force_search() (程序化预执行)               │
  → 直接调用 tavily(query)                           │
  → 结果存入 state.force_search_context              │
        │                                           │
        ▼                                           │
Agent.execute()                                      │
  → 工具绑定 (含 tavily)                             │
  → _build_force_prompt()                            │
    → "用户已启用联网搜索，优先基于搜索结果回答"      │
  → LLM 调用                                         │
        │                                           │
        ▼                                           │
  ← 返回基于搜索结果生成的回答 ◄─────────────────────┘
```

### 2. 知识库 RAG 流程

```
用户选择知识库 "测试下" + 提问 "miniclaw 是什么"
        │
        ▼
前端: selectedKbs=["测试下"], kbRetrievalMode="intent"
        │
        ▼
后端 stream():
  metadata.selected_kbs=["测试下"]
  metadata.kb_retrieval_mode="intent"
        │
        ▼
rag_detect_node():
  → 意图检测: 无 RAG 关键词
  → 但 selected_kbs 存在 → 强制 needs_rag=True
        │
        ▼
should_retrieve() → "rag_retrieve"
        │
        ▼
rag_retrieve_node():
  → 读取 selected_kbs
  → 检索 "测试下" 知识库
  → 返回 rag_context
        │
        ▼
Agent.execute():
  → set_rag_tool_context(selected_kbs)
  → LLM 调用 rag_search 工具时
    → 工具读取上下文 → 使用 "测试下" 而非 "default"
        │
        ▼
  ← 返回基于知识库内容的回答
```

### 3. Skill 工具注入流程

```
应用启动:
  skill_registry.load_all(SkillLoader())
    → 扫描 skills/builtin/*/SKILL.md
    → 解析 YAML frontmatter
    → 注册到 SkillRegistry

Agent 执行:
  _get_tools_from_skills(state)
    → skill_registry.get_for_agent(self.name)
    → 遍历 Skill.tools:
      - 检查 condition (force_search / force_think)
      - 条件匹配 → _load_tool_by_name(tool_def.name)
        → 查找 _base_tools / MCP tools / 动态导入
    → 返回工具列表

  _get_force_tools(state)
    → Skill 工具 + 兜底注入
    → 返回最终强制工具列表
```

## 安装与配置

### 环境要求

- Python >= 3.10
- Node.js >= 18 (前端)
- Ollama (本地模型) 或 OpenAI/DeepSeek API Key

### 后端安装

```bash
# 克隆项目
git clone <repository-url>
cd miniclaw

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -e ".[dev]"
```

### 前端安装

```bash
cd frontend
npm install
npm run dev
```

### 配置

创建 `.env` 文件：

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

# Embedding 配置
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text

# 联网搜索配置
TAVILY_API_KEY=your_tavily_key  # 可选，否则使用 DuckDuckGo

# 天气 API
WEATHER_API_KEY=your_weatherapi_key

# 向量数据库 (可选，默认使用 FAISS)
# MILVUS_HOST=localhost
# MILVUS_PORT=19530

# 其他配置
DEFAULT_CITY=Beijing
LOG_LEVEL=INFO
```

## 使用方式

### CLI 命令

```bash
# 查看帮助
miniclaw --help

# 初始化目录
miniclaw init

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

# 普通对话
response = await app.chat(
    message="今天天气怎么样？",
    user_id="user_001",
    session_id="session_001"
)

# 强制联网搜索
response = await app.chat(
    message="最新的 AI 新闻",
    force_search=True
)

# 使用知识库
response = await app.chat(
    message="miniclaw 是什么？",
    selected_kbs=["测试下"],
    kb_retrieval_mode="force"
)

# 流式输出
async for event in app.stream(
    message="你好",
    force_think=True
):
    print(event)
```

### Web API

```bash
# 流式对话
curl -X POST "http://localhost:9190/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "user_id": "user_001",
    "force_search": false,
    "force_think": false,
    "selected_kbs": ["测试下"],
    "kb_retrieval_mode": "intent"
  }'

# 创建知识库
curl -X POST "http://localhost:9190/knowledge-bases" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试下",
    "description": "测试知识库",
    "embedding_model": "bge-large-zh",
    "embedding_dimension": 1024,
    "similarity_threshold": 0.7
  }'

# 上传文档
curl -X POST "http://localhost:9190/knowledge-bases/测试下/upload" \
  -F "files=@document.pdf"
```

## 开发

```bash
# 代码格式化
black src/
ruff check src/

# 运行测试
pytest tests/

# 前端开发
cd frontend
npm run dev        # 启动开发服务器
npm run build      # 生产构建
```

## 技术栈

| 层级            | 技术                                        |
| ------------- | ----------------------------------------- |
| **AI 框架**     | LangGraph, LangChain                      |
| **LLM 支持**    | Ollama, OpenAI, DeepSeek                  |
| **向量存储**      | FAISS, Milvus                             |
| **Embedding** | Ollama Embeddings, OpenAI Embeddings, BGE |
| **Web 框架**    | FastAPI (后端), Next.js 14 (前端)             |
| **状态管理**      | LangGraph State, React Context            |
| **协议扩展**      | MCP (Model Context Protocol)              |
| **部署**        | Uvicorn, Node.js                          |

## License

MIT
