import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing import Annotated, TypedDict
import operator
import os

from miniclaw.rag.rag_tools import rag_tools


@tool
def calculator(expression: str) -> str:
    """计算数学表达式。输入如 '2+3*4'"""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"计算错误: {e}"


@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    return f"{city}今天晴朗，25°C"


base_tools = [calculator, get_weather]
all_tools = base_tools + rag_tools

load_dotenv()
apiKey = os.getenv("OPENAI_API_KEY", "")
baseUrl = os.getenv("OPENAI_BASE_URL", "https://api.xiaomimimo.com/v1")
model = os.getenv("OPENAI_MODEL", "mimo-v2.5-pro")

llm = ChatOpenAI(
    model=model,
    api_key=apiKey,
    base_url=baseUrl,
    temperature=0,
)
llm_with_tools = llm.bind_tools(all_tools)


async def agent_loop(user_input: str, max_turns: int = 10):
    messages = [HumanMessage(content=user_input)]

    for turn in range(max_turns):
        print(f"\n--- Turn {turn + 1} ---")

        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if response.tool_calls:
            print(f"🔧 模型决定调用 {len(response.tool_calls)} 个工具:")
            for tc in response.tool_calls:
                print(f"   → {tc['name']}({tc['args']})")

            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]

                selected_tool = next(t for t in all_tools if t.name == tool_name)
                result = selected_tool.invoke(tool_args)

                print(f"   ← {str(result)[:200]}")
                messages.append(
                    ToolMessage(content=str(result), tool_call_id=tc["id"])
                )
        else:
            print(f"✅ 最终回答: {response.content}")
            return response.content

    return "达到最大轮次限制"


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    turns: Annotated[int, operator.add]


def call_model(state):
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response], "turns": 1}


def execute_tools(state):
    last = state["messages"][-1]
    print(f"🔧 模型决定调用 {len(last.tool_calls)} 个工具:")
    results = []
    for tc in last.tool_calls:
        selected = next(t for t in all_tools if t.name == tc["name"])
        print(f"   → {tc['name']}({tc['args']})")
        result = selected.invoke(tc["args"])
        result_str = str(result)
        print(f"   ← {result_str[:200]}")
        results.append(ToolMessage(content=result_str, tool_call_id=tc["id"]))
    return {"messages": results}


def should_continue(state):
    last = state["messages"][-1]
    return "tools" if hasattr(last, "tool_calls") and last.tool_calls else END


graph = StateGraph(AgentState)
graph.add_node("model", call_model)
graph.add_node("tools", execute_tools)
graph.set_entry_point("model")
graph.add_conditional_edges("model", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "model")
app = graph.compile()


def chat(user_input: str) -> str:
    """与助手对话"""
    print(f"\n👤 用户：{user_input}")

    messages = [HumanMessage(content=user_input)]
    result = app.invoke({"messages": messages})

    return result["messages"][-1].content


if __name__ == "__main__":
    print(chat("帮我算 123*900等于多少呢"))
