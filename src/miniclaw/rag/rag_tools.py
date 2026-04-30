"""
MiniClaw RAG Tools
LangChain Tool 封装，供 LangGraph Agent 调用
"""

from langchain_core.tools import tool
from miniclaw.rag.service import get_rag_service


@tool
def rag_search(query: str, kb_name: str = "default") -> str:
    """在知识库中搜索相关信息。当用户的问题可能需要参考文档、知识库中的内容时使用此工具。
    Args:
        query: 搜索查询，描述你想查找的信息
        kb_name: 知识库名称，默认为 'default'
    """
    rag = get_rag_service()
    context = rag.get_context(query, kb_name, k=5, max_length=3000)
    if not context:
        return f"知识库 '{kb_name}' 中未找到与 '{query}' 相关的内容。"
    return context


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
