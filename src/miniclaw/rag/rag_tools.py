"""
MiniClaw RAG Tools
LangChain Tool 封装，供 LangGraph Agent 调用
"""

from typing import List, Optional
from langchain_core.tools import tool
from miniclaw.rag.service import get_rag_service

# 线程局部存储，用于传递用户选择的知识库
# 这是工具感知用户选择的桥梁
_tool_context = {}


def set_rag_tool_context(selected_kbs: Optional[List[str]] = None, kb_retrieval_mode: Optional[str] = None):
    """
    设置 RAG 工具的上下文（用户选择的知识库和检索模式）

    在 Agent 执行前调用，让工具知道用户选择了哪些知识库
    """
    _tool_context["selected_kbs"] = selected_kbs
    _tool_context["kb_retrieval_mode"] = kb_retrieval_mode


def get_rag_tool_context() -> dict:
    """获取当前 RAG 工具上下文"""
    return dict(_tool_context)


def clear_rag_tool_context():
    """清除 RAG 工具上下文"""
    _tool_context.clear()


@tool
def rag_search(query: str, kb_name: str = "default") -> str:
    """在知识库中搜索相关信息。当用户的问题可能需要参考文档、知识库中的内容时使用此工具。
    Args:
        query: 搜索查询，描述你想查找的信息
        kb_name: 知识库名称，默认为 'default'
    """
    from loguru import logger

    # 检查是否有用户选择的知识库上下文
    context = get_rag_tool_context()
    selected_kbs = context.get("selected_kbs")

    # 如果用户选择了知识库，优先使用用户选择的；否则使用传入的 kb_name
    if selected_kbs and len(selected_kbs) > 0:
        # TODO 这里注意得迭代成可以选择多个知识库 使用第一个选择的知识库（或者可以搜索多个）
        target_kb = selected_kbs[0]
        logger.info(f"[rag_search tool] User selected KBs: {selected_kbs}, overriding kb_name='{kb_name}' -> '{target_kb}'")
        kb_name = target_kb
    else:
        logger.info(f"[rag_search tool] Called with query='{query[:50]}...', kb_name='{kb_name}'")

    rag = get_rag_service()
    context_text = rag.get_context(query, kb_name, k=5, max_length=3000)
    if not context_text:
        logger.warning(f"[rag_search tool] No context found in KB '{kb_name}'")
        return f"知识库 '{kb_name}' 中未找到与 '{query}' 相关的内容。"
    logger.info(f"[rag_search tool] Returning context: {len(context_text)} chars")
    return context_text


@tool
def rag_add_documents(file_paths: str, kb_name: str = "default") -> str:
    """将文档添加到知识库中，支持 PDF、TXT、MD 等格式。多个文件路径用逗号分隔。
    Args:
        file_paths: 文件路径，多个路径用逗号分隔
        kb_name: 知识库名称，默认为 'default'
    """
    rag = get_rag_service()
    kb = rag.get_kb(kb_name)
    if kb is None:
        kb = rag.create_kb(kb_name)

    paths = [p.strip() for p in file_paths.split(",") if p.strip()]
    count = kb.add_files(paths)

    if count > 0:
        return f"成功将 {count} 个文档块添加到知识库 '{kb_name}'"
    return f"未能添加任何文档，请检查文件路径是否正确"


@tool
def rag_add_directory(directory: str, kb_name: str = "default") -> str:
    """将目录下的所有文档添加到知识库中，支持递归扫描子目录。
    Args:
        directory: 目录路径
        kb_name: 知识库名称，默认为 'default'
    """
    rag = get_rag_service()
    kb = rag.get_kb(kb_name)
    if kb is None:
        kb = rag.create_kb(kb_name)

    count = kb.add_directory(directory, recursive=True)

    if count > 0:
        return f"成功将 {count} 个文档块添加到知识库 '{kb_name}'"
    return f"未能从目录 '{directory}' 添加任何文档"


@tool
def rag_list_kbs() -> str:
    """列出所有可用的知识库"""
    rag = get_rag_service()
    kbs = rag.list_kbs()
    if not kbs:
        return "当前没有知识库。使用 rag_add_documents 或 rag_add_directory 创建知识库。"
    return "可用知识库:\n" + "\n".join(f"  - {name}" for name in kbs)


@tool
def rag_delete_kb(kb_name: str) -> str:
    """删除指定的知识库及其所有文档。
    Args:
        kb_name: 要删除的知识库名称
    """
    rag = get_rag_service()
    if rag.delete_kb(kb_name):
        return f"知识库 '{kb_name}' 已删除"
    return f"知识库 '{kb_name}' 不存在或删除失败"


rag_tools = [rag_search, rag_add_documents, rag_add_directory, rag_list_kbs, rag_delete_kb]
