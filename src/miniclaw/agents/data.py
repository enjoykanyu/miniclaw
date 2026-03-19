"""
MiniClaw Data Agent
Handles Excel operations and data processing
"""

from typing import Optional, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from miniclaw.agents.base import BaseAgent
from miniclaw.core.state import MiniClawState
from miniclaw.utils.helpers import load_prompt_template, format_datetime


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
    name = "data_agent"
    description = "数据处理助手，操作Excel表格、数据分析、自然语言转数据操作"
    
    def __init__(self, llm=None, tools=None):
        if tools is None:
            tools = [create_excel_file, read_excel_file, analyze_data, update_excel_cell]
        super().__init__(llm=llm, tools=tools)
        self._prompts = load_prompt_template("data")
    
    async def process(self, state: MiniClawState) -> str:
        user_message = self.get_last_user_message(state)
        
        system_prompt = self._prompts.get("system", "")
        
        llm_with_tools = self.bind_tools()
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        
        response = await llm_with_tools.ainvoke(messages)
        
        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_messages = []
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                for tool in self._tools:
                    if tool.name == tool_name:
                        result = tool.invoke(tool_args)
                        tool_messages.append(str(result))
            
            return "\n\n".join(tool_messages) if tool_messages else response.content
        
        return response.content
