# MiniClaw

MiniClaw - Enterprise-grade Multi-Agent AI Assistant Platform, built on LangGraph multi-agent architecture and LangChain ecosystem, supporting deep thinking, web search, knowledge base RAG, MCP protocol extension, Skill system and other advanced capabilities.

**English** | [中文](README.md) | [日本語](README_JP.md) | [한국어](README_KR.md)

## Core Features

### Multi-Agent Collaboration System

- **Supervisor-Worker Architecture** - Based on LangGraph's supervisor-executor pattern, Supervisor handles task routing, Workers handle domain-specific execution
- **6 Professional Agents** - Chat (conversation), Task (task management), Info (information query), Learning (learning assistance), Health (health consultation), Data (data analysis)
- **Dynamic Tool Injection** - Supports conditional Skill injection and forced tool injection (deep thinking, web search)

### Knowledge Base & RAG

- **Enterprise-grade Knowledge Base Management** - Create, configure, and delete knowledge bases with customizable embedding models, reranking models, and chunking strategies
- **Hybrid Retrieval Engine** - Dense vector retrieval + BM25 keyword retrieval + RRF fusion algorithm
- **Multiple Vector Storage Backends** - FAISS (local) and Milvus (production-grade)
- **Multi-format Document Support** - PDF, Markdown, TXT, Word parsing and vectorization
- **Intent Recognition / Forced Retrieval** - Automatic judgment or forced knowledge base retrieval

### Tools & Extensions

- **MCP Protocol Support** - Model Context Protocol, connecting external tools and services
- **Skill System** - Based on SKILL.md declarative configuration, conditional tool injection
- **Forced Web Search** - Tavily API / DuckDuckGo dual backends, programmatic pre-execution search
- **Deep Thinking Mode** - Force invocation of think tool for structured reasoning
- **Built-in Tools** - Weather query, news retrieval, reminder management, Excel processing, etc.

### Frontend Interaction

- **Next.js 14 + React** - Modern frontend architecture
- **Streaming Response** - SSE real-time output with thinking process visualization
- **Knowledge Base Management UI** - Drag-and-drop upload, configuration management, retrieval mode switching
- **Multi-session Management** - Session creation, renaming, history tracking

## Business Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Interaction Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Chat UI    │  │   KB Mgmt   │  │   Session   │  │   Agent Settings    │ │
│  │ ChatPanel   │  │  KB Panel   │  │  Session    │  │   Settings Panel    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         └─────────────────┴─────────────────┴────────────────────┘            │
│                                    │                                         │
│                              HTTP / SSE                                      │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼─────────────────────────────────────────┐
│                              API Gateway Layer                                │
│                                    │                                         │
│  ┌─────────────────────────────────┴─────────────────────────────────────┐   │
│  │                    FastAPI RESTful API                                  │   │
│  │  /chat/stream  /chat  /knowledge-bases  /sessions  /tools  /mcp       │   │
│  └─────────────────────────────────┬─────────────────────────────────────┘   │
│                                    │                                         │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼─────────────────────────────────────────┐
│                           LangGraph Workflow Engine                           │
│                                    │                                         │
│  ┌─────────────────────────────────┴─────────────────────────────────────┐   │
│  │                         Supervisor Routing Node                         │   │
│  │  Input: User message + metadata(force_think, force_search, selected_kbs)│   │
│  │  Output: Command(goto=WorkerType)                                        │   │
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
│  │ (KB Retrieval)  │  │ (Tool Execution)│                                    │
│  └─────────────────┘  └─────────────────┘                                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼─────────────────────────────────────────┐
│                              Capability Extension Layer                       │
│                                    │                                         │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐   │
│  │         Skill System              │         MCP Protocol Extension       │   │
│  │  ┌─────────────────────────┐    │    ┌─────────────────────────┐     │   │
│  │  │  SKILL.md Declarative   │    │    │  MCP Server Connection  │     │   │
│  │  │  - agent binding        │    │    │  - STDIO / SSE Transport│     │   │
│  │  │  - tools conditional    │    │    │  - Tool Discovery       │     │   │
│  │  │  - condition triggers   │    │    │  - OAuth Auth           │     │   │
│  │  └─────────────────────────┘    │    └─────────────────────────┘     │   │
│  └─────────────────────────────────┴─────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼─────────────────────────────────────────┐
│                              Infrastructure Layer                             │
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

## Technical Architecture

### Backend Architecture

```
src/miniclaw/
├── agents/                    # Multi-Agent System
│   ├── supervisor.py          # Supervisor Agent - Task routing and distribution
│   ├── worker.py              # BaseWorker - Worker base class, tool injection and execution
│   ├── chat.py                # Chat Agent - General conversation
│   ├── info.py                # Info Agent - Information query (weather, news, RAG)
│   ├── task.py                # Task Agent - Task management
│   ├── learning.py            # Learning Agent - Learning assistance
│   ├── health.py              # Health Agent - Health consultation
│   ├── data.py                # Data Agent - Data analysis
│   └── base.py                # Agent base class definition
│
├── core/                      # Core Engine
│   ├── graph.py               # LangGraph workflow definition (MiniClawApp)
│   ├── state.py               # State definition (MiniClawState)
│   ├── router.py              # Routing logic
│   ├── error_handler.py       # Error handling and retry
│   └── exceptions.py          # Exception definitions
│
├── rag/                       # RAG Retrieval Augmented System
│   ├── service.py             # RAGService - Knowledge base management and retrieval entry
│   ├── vectorstore.py         # FAISS/Milvus vector storage implementation
│   ├── embeddings.py          # Embedding service (Ollama/OpenAI/HF)
│   ├── retriever.py           # HybridRetriever - Hybrid retrieval (Dense+BM25+RRF)
│   ├── rag_node.py            # LangGraph RAG node (detect/retrieve/generate)
│   ├── rag_tools.py           # RAG tools (rag_search etc.)
│   ├── document_loader.py     # Document loading and parsing
│   ├── chunking.py            # Document chunking strategies
│   └── knowledge_manager.py   # Knowledge base management
│
├── skills/                    # Skill System
│   ├── registry.py            # SkillRegistry - Global singleton registry
│   ├── loader.py              # SkillLoader - SKILL.md parser
│   └── builtin/               # Built-in Skills
│       └── web_search/        # Web search Skill
│           └── SKILL.md       # Declarative configuration (agent/tools/condition)
│
├── mcp/                       # MCP Protocol Implementation
│   ├── manager.py             # MCP connection management
│   ├── client.py              # MCP client
│   ├── tools.py               # MCP tool registration and discovery
│   └── protocol.py            # MCP protocol definition
│
├── tools/                     # Tool Set
│   ├── tavily.py              # Tavily web search
│   ├── think.py               # Deep thinking tool
│   ├── weather.py             # Weather query
│   ├── news.py                # News retrieval
│   ├── reminder.py            # Reminder management
│   ├── scheduler.py           # Scheduled tasks
│   ├── excel.py               # Excel processing
│   └── builtin/               # Built-in tools
│
├── memory/                    # Memory System
│   ├── short_term.py          # Short-term memory
│   ├── mid_term.py            # Mid-term memory
│   ├── long_term.py           # Long-term memory
│   └── checkpointer.py        # State checkpoint
│
├── config/                    # Configuration Management
│   ├── settings.py            # Global configuration (Pydantic Settings)
│   └── prompts/               # Prompt templates
│
└── api.py                     # FastAPI main entry
```

### Frontend Architecture

```
frontend/src/
├── app/                       # Next.js App Router
│   ├── page.tsx               # Main page
│   └── layout.tsx             # Root layout
│
├── components/
│   ├── chat/                  # Chat components
│   │   ├── ChatPanel.tsx      # Chat panel main component
│   │   ├── ChatInput.tsx      # Input box (tool toggles, KB selection)
│   │   ├── ChatMessage.tsx    # Message rendering
│   │   ├── ThoughtChain.tsx   # Thinking process visualization
│   │   └── RetrievalCard.tsx  # Retrieval result cards
│   │
│   ├── knowledge/             # Knowledge base management
│   │   ├── KnowledgeBasePanel.tsx   # Knowledge base grid list
│   │   ├── KbCreateModal.tsx        # Create knowledge base modal
│   │   └── KbDetailPanel.tsx        # Knowledge base detail (upload/manage)
│   │
│   ├── layout/                # Layout components
│   │   ├── Navbar.tsx         # Top navigation
│   │   ├── Sidebar.tsx        # Sidebar
│   │   └── ResizeHandle.tsx   # Drag to resize
│   │
│   └── editor/                # Editor components
│       └── InspectorPanel.tsx # Inspector panel
│
└── lib/
    ├── api.ts                 # API client (streamChat etc.)
    └── store.tsx              # React Context global state management
```

## Core Workflows

### 1. Forced Web Search Workflow

```
User clicks "Web Search" button
        │
        ▼
Frontend: forceSearch=true ─────────────────────────────┐
        │                                               │
        ▼                                               │
Backend stream():                                       │
  metadata.force_search=true                             │
        │                                               │
        ▼                                               │
_worker._get_force_tools()                               │
  → Skill conditional injection: web_search Skill        │
    → condition=force_search match                       │
    → _load_tool_by_name("tavily")                        │
  → Fallback injection: tavily tool                      │
        │                                               │
        ▼                                               │
_execute_force_search() (Programmatic pre-execution)     │
  → Direct call tavily(query)                            │
  → Store results in state.force_search_context          │
        │                                               │
        ▼                                               │
Agent.execute()                                          │
  → Tool binding (includes tavily)                       │
  → _build_force_prompt()                                │
    → "User enabled web search, prioritize search results"
  → LLM call                                             │
        │                                               │
        ▼                                               │
  ← Return answer based on search results ◄─────────────┘
```

### 2. Knowledge Base RAG Workflow

```
User selects KB "test" + asks "what is miniclaw"
        │
        ▼
Frontend: selectedKbs=["test"], kbRetrievalMode="intent"
        │
        ▼
Backend stream():
  metadata.selected_kbs=["test"]
  metadata.kb_retrieval_mode="intent"
        │
        ▼
rag_detect_node():
  → Intent detection: no RAG keywords
  → But selected_kbs exists → force needs_rag=True
        │
        ▼
should_retrieve() → "rag_retrieve"
        │
        ▼
rag_retrieve_node():
  → Read selected_kbs
  → Retrieve "test" knowledge base
  → Return rag_context
        │
        ▼
Agent.execute():
  → set_rag_tool_context(selected_kbs)
  → LLM calls rag_search tool
    → Tool reads context → uses "test" instead of "default"
        │
        ▼
  ← Return answer based on knowledge base content
```

### 3. Skill Tool Injection Workflow

```
Application startup:
  skill_registry.load_all(SkillLoader())
    → Scan skills/builtin/*/SKILL.md
    → Parse YAML frontmatter
    → Register to SkillRegistry

Agent execution:
  _get_tools_from_skills(state)
    → skill_registry.get_for_agent(self.name)
    → Iterate Skill.tools:
      - Check condition (force_search / force_think)
      - Condition match → _load_tool_by_name(tool_def.name)
        → Find _base_tools / MCP tools / dynamic import
    → Return tool list

  _get_force_tools(state)
    → Skill tools + fallback injection
    → Return final forced tool list
```

## Installation & Configuration

### Requirements

- Python >= 3.10
- Node.js >= 18 (Frontend)
- Ollama (local models) or OpenAI/DeepSeek API Key

### Backend Installation

```bash
# Clone project
git clone <repository-url>
cd miniclaw

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e ".[dev]"
```

### Frontend Installation

```bash
cd frontend
npm install
npm run dev
```

### Configuration

Create `.env` file:

```bash
# LLM Configuration (default uses Ollama)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:1.7b

# Optional: OpenAI Configuration
# OPENAI_API_KEY=your_openai_key
# OPENAI_MODEL=gpt-4o-mini

# Optional: DeepSeek Configuration
# DEEPSEEK_API_KEY=your_deepseek_key
# DEEPSEEK_MODEL=deepseek-chat

# Embedding Configuration
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text

# Web Search Configuration
TAVILY_API_KEY=your_tavily_key  # Optional, otherwise uses DuckDuckGo

# Weather API
WEATHER_API_KEY=your_weatherapi_key

# Vector Database (Optional, default uses FAISS)
# MILVUS_HOST=localhost
# MILVUS_PORT=19530

# Other Configuration
DEFAULT_CITY=Beijing
LOG_LEVEL=INFO
```

## Usage

### CLI Commands

```bash
# Show help
miniclaw --help

# Initialize directory
miniclaw init

# Test LLM connection
miniclaw test-llm

# Single message chat
miniclaw chat "Hello"

# Interactive chat
miniclaw interactive

# Start web service
miniclaw serve
miniclaw serve --host 0.0.0.0 --port 9190 --reload
```

### Python API

```python
from miniclaw.core.graph import MiniClawApp

app = MiniClawApp()

# Normal chat
response = await app.chat(
    message="How's the weather today?",
    user_id="user_001",
    session_id="session_001"
)

# Forced web search
response = await app.chat(
    message="Latest AI news",
    force_search=True
)

# Use knowledge base
response = await app.chat(
    message="What is miniclaw?",
    selected_kbs=["test"],
    kb_retrieval_mode="force"
)

# Streaming output
async for event in app.stream(
    message="Hello",
    force_think=True
):
    print(event)
```

### Web API

```bash
# Streaming chat
curl -X POST "http://localhost:9190/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "user_id": "user_001",
    "force_search": false,
    "force_think": false,
    "selected_kbs": ["test"],
    "kb_retrieval_mode": "intent"
  }'

# Create knowledge base
curl -X POST "http://localhost:9190/knowledge-bases" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test",
    "description": "Test knowledge base",
    "embedding_model": "bge-large-en",
    "embedding_dimension": 1024,
    "similarity_threshold": 0.7
  }'

# Upload document
curl -X POST "http://localhost:9190/knowledge-bases/test/upload" \
  -F "files=@document.pdf"
```

## Development

```bash
# Code formatting
black src/
ruff check src/

# Run tests
pytest tests/

# Frontend development
cd frontend
npm run dev        # Start dev server
npm run build      # Production build
```

## Tech Stack

| Layer            | Technology                                |
| ---------------- | ----------------------------------------- |
| **AI Framework** | LangGraph, LangChain                      |
| **LLM Support**  | Ollama, OpenAI, DeepSeek                  |
| **Vector Store** | FAISS, Milvus                             |
| **Embedding**    | Ollama Embeddings, OpenAI Embeddings, BGE |
| **Web Framework**| FastAPI (Backend), Next.js 14 (Frontend)  |
| **State Management**| LangGraph State, React Context         |
| **Protocol Extension** | MCP (Model Context Protocol)         |
| **Deployment**   | Uvicorn, Node.js                          |

## License

MIT
