"""
Think Tool - 深度思考工具

当用户强制启用深度思考时，此工具被注入到 Agent 的工具列表中。
模型会在生成最终回复前，先调用此工具进行结构化思考。
"""

from langchain_core.tools import tool


@tool
def think(thought: str) -> str:
    """
    深度思考工具。在回答复杂问题前，使用此工具进行逐步推理和分析。

    你应该：
    1. 分析用户问题的核心要点
    2. 列出需要考虑的各个方面
    3. 评估不同角度的信息
    4. 形成清晰的推理链条
    5. 基于推理得出初步结论

    Args:
        thought: 你的完整思考过程，包含分析、推理和结论

    Returns:
        思考结果的确认
    """
    return f"[深度思考完成]\n\n{thought}\n\n现在请基于以上思考，给用户一个完整、准确的回复。"
