"""
MiniClaw RAG Node — LangGraph 中的 RAG 节点

参考:
  - agent-service-toolkit: 三节点线性流程 (retrieve → augment → generate)
  - SuperMew: 四节点条件分支 (retrieve → grade → rewrite/answer)
  - deer-flow: Middleware 链注入模式

RAG 节点流程:
  1. rag_detect_node — 自动识别是否需要 RAG 检索
  2. rag_retrieve_node — 执行混合检索 (Dense + BM25 + RRF)
  3. rag_generate_node — 基于检索结果生成回答

集成方式:
  方式一 (Node-based): 在 LangGraph 中添加 RAG 节点
  方式二 (Tool-based): Agent 通过 rag_search 工具调用
"""

from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from loguru import logger

from miniclaw.core.state import MiniClawState
from miniclaw.rag.service import get_rag_service
from miniclaw.rag.retriever import HybridRetriever, SearchMode, FusionMethod
from miniclaw.rag.types import RetrievalResult

RAG_KEYWORDS = [
    "知识库", "文档", "资料", "文件", "PDF", "pdf",
    "文章", "论文", "报告", "手册", "指南", "教程",
    "help", "document", "knowledge",
]

RAG_SYSTEM_PROMPT = """你是一个知识库问答助手。请基于以下检索到的参考资料回答用户的问题。

要求：
1. 优先使用参考资料中的信息回答
2. 如果参考资料不足以回答问题，请明确说明
3. 引用来源时标注 [来源X]
4. 不要编造参考资料中没有的信息

参考资料：
{context}"""


def detect_rag_need(query: str, strategy: str = "hybrid") -> bool:
    """
    自动识别是否需要 RAG 检索

    策略:
      - keyword: 关键词匹配（快速，零成本）
      - hybrid: 关键词 + 启发式规则（推荐）
      - llm: LLM 分类（最准确，有成本）
    """
    if strategy == "keyword":
        return _keyword_detect(query)
    elif strategy == "llm":
        return _keyword_detect(query)
    else:
        return _hybrid_detect(query)


def _keyword_detect(query: str) -> bool:
    query_lower = query.lower()
    return any(kw in query_lower for kw in RAG_KEYWORDS)


def _hybrid_detect(query: str) -> bool:
    if _keyword_detect(query):
        return True

    rag_context_patterns = ["文档说", "资料中", "文件里", "书上", "论文中", "手册里"]
    if any(p in query for p in rag_context_patterns):
        return True

    return False


async def rag_detect_node(state: MiniClawState) -> Dict[str, Any]:
    """
    RAG 检测节点 — 判断当前查询是否需要知识库检索

    输入: state.messages (用户消息)
    输出: state.needs_rag (True/False)
    """
    messages = state.get("messages", [])
    if not messages:
        logger.info("[RAG Detect] No messages, skipping RAG")
        return {"needs_rag": False}

    last_human_msg = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_human_msg = msg.content
            break

    if not last_human_msg:
        logger.info("[RAG Detect] No human message found")
        return {"needs_rag": False}

    metadata = state.get("metadata") or {}
    selected_kbs = metadata.get("selected_kbs")
    kb_retrieval_mode = metadata.get("kb_retrieval_mode", "intent")

    logger.info(f"[RAG Detect] query='{last_human_msg[:50]}...', selected_kbs={selected_kbs}, mode={kb_retrieval_mode}")

    # 如果用户手动选择了知识库且设置为强制检索模式，直接返回True
    if selected_kbs and kb_retrieval_mode == "force":
        logger.info(f"[RAG Detect] Force retrieval mode with selected KBs: {selected_kbs}")
        return {"needs_rag": True}

    # 如果用户手动选择了知识库但使用意图识别模式，仍然做检测
    if selected_kbs and kb_retrieval_mode == "intent":
        needs_rag = detect_rag_need(last_human_msg, strategy="hybrid")
        # TODO 用户手动选择了知识库，但意图识别未命中，这里得对比下强制检索的区别
        if not needs_rag:
            logger.info(f"[RAG Detect] Intent detection returned False, but user selected KBs {selected_kbs}, forcing RAG")
            needs_rag = True
        logger.info(f"[RAG Detect] Intent detection with selected_kbs: needs_rag={needs_rag}")
        return {"needs_rag": needs_rag}

    # 默认行为：自动检测
    needs_rag = detect_rag_need(last_human_msg, strategy="hybrid")
    logger.info(f"[RAG Detect] Auto detection: needs_rag={needs_rag}")
    return {"needs_rag": needs_rag}


async def rag_retrieve_node(state: MiniClawState) -> Dict[str, Any]:
    """
    RAG 检索节点 — 执行混合检索

    输入: state.messages + state.needs_rag
    输出: state.rag_context + state.rag_sources
    """
    messages = state.get("messages", [])
    if not messages:
        logger.info("[RAG Retrieve] No messages")
        return {"rag_context": "", "rag_sources": []}

    last_human_msg = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_human_msg = msg.content
            break

    if not last_human_msg:
        logger.info("[RAG Retrieve] No human message")
        return {"rag_context": "", "rag_sources": []}

    logger.info(f"[RAG Retrieve] query='{last_human_msg[:50]}...'")

    rag_service = get_rag_service()
    kb_names = rag_service.list_kbs()
    logger.info(f"[RAG Retrieve] Available KBs: {kb_names}")

    if not kb_names:
        logger.warning("[RAG Retrieve] No knowledge bases available")
        return {"rag_context": "", "rag_sources": []}

    # 获取用户选择的知识库
    metadata = state.get("metadata") or {}
    selected_kbs = metadata.get("selected_kbs")
    logger.info(f"[RAG Retrieve] selected_kbs from metadata: {selected_kbs}")

    # 如果用户选择了特定知识库，只检索这些；否则检索所有
    if selected_kbs and len(selected_kbs) > 0:
        target_kbs = [name for name in selected_kbs if name in kb_names]
        if not target_kbs:
            logger.warning(f"[RAG Retrieve] Selected KBs not found: {selected_kbs}, falling back to all KBs")
            target_kbs = kb_names
    else:
        target_kbs = kb_names

    logger.info(f"[RAG Retrieve] Target KBs: {target_kbs}")

    all_results: List[RetrievalResult] = []
    for kb_name in target_kbs:
        try:
            kb = rag_service.get_kb(kb_name)
            if kb is None:
                logger.warning(f"[RAG Retrieve] KB '{kb_name}' not found in service")
                continue
            logger.info(f"[RAG Retrieve] Searching KB '{kb_name}'...")
            results = kb.search(last_human_msg, k=3)
            logger.info(f"[RAG Retrieve] KB '{kb_name}' returned {len(results)} results")
            all_results.extend(results)
        except Exception as e:
            logger.error(f"[RAG Retrieve] RAG search failed for KB '{kb_name}': {e}")

    all_results.sort(key=lambda r: r.score, reverse=True)
    top_results = all_results[:5]

    logger.info(f"[RAG Retrieve] Total results after merge: {len(all_results)}, top 5 selected")

    if not top_results:
        logger.warning("[RAG Retrieve] No results found across all KBs")
        return {"rag_context": "", "rag_sources": []}

    context_parts = []
    sources = []
    for i, result in enumerate(top_results):
        context_parts.append(f"[来源{i+1}: {result.source} (相关度:{result.score:.2f})]\n{result.content}")
        sources.append({
            "source": result.source,
            "score": result.score,
            "content_preview": result.content[:100],
        })

    context = "\n\n".join(context_parts)
    logger.info(f"[RAG Retrieve] Context built: {len(context)} chars from {len(top_results)} sources")
    return {"rag_context": context, "rag_sources": sources}


async def rag_generate_node(state: MiniClawState) -> Dict[str, Any]:
    """
    RAG 生成节点 — 基于检索结果生成回答

    输入: state.messages + state.rag_context
    输出: state.agent_response (更新 messages)
    """
    rag_context = state.get("rag_context", "")
    if not rag_context:
        return {"agent_response": "抱歉，知识库中未找到相关信息。"}

    messages = state.get("messages", [])
    user_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break

    system_prompt = RAG_SYSTEM_PROMPT.format(context=rag_context)

    from miniclaw.config.settings import settings
    from miniclaw.llm.factory import create_llm

    try:
        llm = create_llm()
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_query),
        ])
        return {"agent_response": response.content}
    except Exception as e:
        logger.error(f"RAG generate failed: {e}")
        return {"agent_response": f"基于知识库检索到以下内容，但生成回答时出错：\n\n{rag_context}"}


def should_retrieve(state: MiniClawState) -> str:
    """条件边：判断是否需要进入 RAG 检索"""
    metadata = state.get("metadata") or {}
    selected_kbs = metadata.get("selected_kbs")
    kb_retrieval_mode = metadata.get("kb_retrieval_mode", "intent")
    needs_rag = state.get("needs_rag", False)

    logger.info(f"[should_retrieve] selected_kbs={selected_kbs}, mode={kb_retrieval_mode}, needs_rag={needs_rag}, force_search={metadata.get('force_search')}")

    if metadata.get("force_search"):
        logger.info("[should_retrieve] force_search=True, skipping RAG, routing to supervisor")
        return "skip_rag"

    # 如果用户手动选择了知识库且设置为强制检索模式，强制进入RAG
    if selected_kbs and kb_retrieval_mode == "force":
        logger.info(f"[should_retrieve] KB force retrieval mode with selected KBs: {selected_kbs}")
        return "rag_retrieve"

    if needs_rag:
        logger.info("[should_retrieve] needs_rag=True, routing to rag_retrieve")
        return "rag_retrieve"

    logger.info("[should_retrieve] No RAG needed, routing to skip_rag")
    return "skip_rag"
