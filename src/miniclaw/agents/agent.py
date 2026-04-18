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
# ─── 1. 定义工具 ───
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

tools = [calculator, get_weather]
load_dotenv()  # 自动加载 .env 文件
apiKey = os.getenv("OLLAMA_API_KEY", "ollama")  # Ollama不需要真实密钥
baseUrl = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")  # 可选: deepseek-r1:8b, qwen3:1.7b
    
# Configure model
llm = ChatOpenAI(
   model=model,
    api_key=apiKey,
    base_url=baseUrl,
    temperature=0
)
llm_with_tools = llm.bind_tools(tools)

# ─── 2. Agent Loop 核心 ───
async def agent_loop(user_input: str, max_turns: int = 10):
    messages = [HumanMessage(content=user_input)]

    for turn in range(max_turns):
        print(f"\n--- Turn {turn + 1} ---")

        # 调用 LLM
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        # 检查是否有工具调用
        if response.tool_calls:
            print(f"🔧 模型决定调用 {len(response.tool_calls)} 个工具:")
            for tc in response.tool_calls:
                print(f"   → {tc['name']}({tc['args']})")

            # 执行每个工具
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]

                # 找到对应工具并执行
                selected_tool = next(t for t in tools if t.name == tool_name)
                result = selected_tool.invoke(tool_args)

                print(f"   ← {result}")
                messages.append(
                    ToolMessage(content=str(result), tool_call_id=tc["id"])
                )
            # 继续下一轮循环
        else:
            # 无工具调用 → 返回最终答案
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
    """执行工具调用"""
    last = state["messages"][-1]   
    print(f"🔧 模型决定调用 {len(last.tool_calls)} 个工具:")
    results = []
    for tc in last.tool_calls:
        selected = next(t for t in tools if t.name == tc["name"])
        print(f"   → {tc['name']}({tc['args']})工具 {selected.name}")
        result = selected.invoke(tc["args"])
        results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return {"messages": results}

def should_continue(state):
    last = state["messages"][-1]
    return "tools" if hasattr(last, 'tool_calls') and last.tool_calls else END
#编排图节点
graph = StateGraph(AgentState) # 创建图，指定状态类型为 AgentState
graph.add_node("model", call_model) # 添加 model 节点
graph.add_node("tools", execute_tools) # 添加 tools 节点
graph.set_entry_point("model") # 设置入口点为 model
graph.add_conditional_edges("model", should_continue, {"tools": "tools", END: END}) # 添加条件边，根据 should_continue 判断是否继续调用 tools
graph.add_edge("tools", "model") #增加边 tools 节点执行完后， 无条件 回到 model
app = graph.compile() # 编译图 把声明式的图编译成可执行的 app

def chat(user_input: str) -> str:
    """与助手对话"""
    print(f"\n👤 用户：{user_input}")
    
    messages = [HumanMessage(content=user_input)]
    result = app.invoke({"messages": messages})
    
    return result["messages"][-1].content
# ─── 3. 运行 ───
if __name__ == "__main__":
    # asyncio.run(agent_loop("北京和上海的天气怎么样？另外帮我算一下 123*456"))
    # print(chat("北京和上海的天气怎么样？另外帮我算一下 2的32次方"))
    result = chat("帮我算 123*900等于多少呢")
    print(result)
