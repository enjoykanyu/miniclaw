"""
MiniClaw Data Agent
Handles Excel operations and data processing
"""

from typing import Optional, List, Any

from langchain_core.tools import tool

from miniclaw.agents.base import BaseAgent
from miniclaw.utils.helpers import load_prompt_template


@tool
def create_excel_file(filename: str, columns: List[str], data: Optional[List[List]] = None) -> str:
    """
    Create a new Excel file with specified columns.

    Args:
        filename: Name of the file (without .xlsx extension)
        columns: List of column names
        data: Optional initial data rows

    Returns:
        Path to the created file
    """
    from miniclaw.tools.excel import create_excel

    try:
        filepath = create_excel(filename, columns, data)
        return f"✅ Excel文件已创建: {filepath}"
    except Exception as e:
        return f"❌ 创建失败: {str(e)}"


@tool
def read_excel_file(filename: str) -> str:
    """
    Read and display Excel file contents.

    Args:
        filename: Name of the file to read

    Returns:
        File contents summary
    """
    from miniclaw.tools.excel import read_excel

    try:
        data = read_excel(filename)
        return f"📊 文件内容:\n{data}"
    except Exception as e:
        return f"❌ 读取失败: {str(e)}"


@tool
def analyze_data(filename: str, analysis_type: str, column: Optional[str] = None) -> str:
    """
    Perform data analysis on Excel file.

    Args:
        filename: Name of the file to analyze
        analysis_type: Type of analysis - "summary", "count", "sum", "average", "sort"
        column: Column to analyze (optional)

    Returns:
        Analysis results
    """
    from miniclaw.tools.excel import analyze_excel

    try:
        result = analyze_excel(filename, analysis_type, column)
        return f"📈 分析结果:\n{result}"
    except Exception as e:
        return f"❌ 分析失败: {str(e)}"


@tool
def update_excel_cell(filename: str, row: int, column: str, value: str) -> str:
    """
    Update a cell in Excel file.

    Args:
        filename: Name of the file
        row: Row number (1-indexed)
        column: Column name
        value: New value

    Returns:
        Confirmation message
    """
    from miniclaw.tools.excel import update_cell

    try:
        update_cell(filename, row, column, value)
        return f"✅ 已更新 {filename} 第{row}行 {column}列 为: {value}"
    except Exception as e:
        return f"❌ 更新失败: {str(e)}"


class DataAgent(BaseAgent):
    """
    数据处理智能体

    功能：
    - 创建 Excel 文件
    - 读取 Excel 内容
    - 数据分析（汇总、计数、平均值等）
    - 更新单元格
    """

    name = "data_agent"
    description = "数据处理助手，操作Excel表格、数据分析、自然语言转数据操作"

    def __init__(self, llm=None, tools=None, use_react: bool = False):
        if tools is None:
            tools = [create_excel_file, read_excel_file, analyze_data, update_excel_cell]
        super().__init__(llm=llm, tools=tools, use_react=use_react)
        self._prompts = load_prompt_template("data")

    def _get_system_prompt(self) -> str:
        """获取数据处理的系统提示词"""
        return self._prompts.get("system", """你是数据处理助手，帮助用户操作 Excel 文件和进行数据分析。

你可以：
1. 创建新的 Excel 文件
2. 读取 Excel 文件内容
3. 进行数据分析（汇总、计数、平均值、排序等）
4. 更新 Excel 单元格

请帮助用户高效地处理数据。""")

    def format_tool_result(self, tool_name: str, result: Any) -> Optional[str]:
        """
        自定义工具结果格式化

        针对数据处理工具的特殊格式化
        """
        if tool_name == "create_excel_file":
            return str(result)

        elif tool_name == "read_excel_file":
            return str(result)

        elif tool_name == "analyze_data":
            return str(result)

        elif tool_name == "update_excel_cell":
            return str(result)

        # 返回 None 使用默认格式化
        return None
