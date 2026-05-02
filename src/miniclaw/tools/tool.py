import asyncio
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

CONCURRENCY_SAFE = {"read_file", "grep_search", "list_files"}
READONLY_TOOLS = {"read_file", "grep_search", "list_files", "web_search"}

@tool
def read_file(path: str) -> str:
    """读取文件内容"""
    try: return open(path).read()[:5000]
    except Exception as e: return f"错误: {e}"

@tool
def write_file(path: str, content: str) -> str:
    """写入文件"""
    try:
        open(path, 'w').write(content)
        return f"已写入 {path}"
    except Exception as e: return f"错误: {e}"

@tool
def bash(command: str) -> str:
    """执行shell命令"""
    import subprocess
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout[:5000] or result.stderr

tools = [read_file, write_file, bash]

def check_permission(tool_name, args, mode="default"):
    if mode == "plan" and tool_name not in READONLY_TOOLS:
        return {"action": "deny", "message": "Plan模式只允许只读工具"}
    if tool_name == "bash" and any(w in args.get("command","") for w in ["rm ", "delete", "drop"]):
        return {"action": "confirm", "message": f"⚠️ 危险命令: {args['command']}"}
    return {"action": "allow"}

async def execute_tools_parallel(tool_calls, mode="default"):
    results = []
    safe_batch = []
    for tc in tool_calls:
        perm = check_permission(tc["name"], tc["args"], mode)
        if perm["action"] == "deny":
            results.append(ToolMessage(content=perm["message"], tool_call_id=tc["id"]))
        elif perm["action"] == "confirm":
            answer = input(f"{perm['message']} 允许?(y/n): ")
            if answer.lower() != 'y':
                results.append(ToolMessage(content="用户拒绝", tool_call_id=tc["id"]))
                continue
            selected = next(t for t in tools if t.name == tc["name"])
            result = selected.invoke(tc["args"])
            results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
        else:
            selected = next(t for t in tools if t.name == tc["name"])
            if tc["name"] in CONCURRENCY_SAFE:
                safe_batch.append((tc, selected))
            else:
                result = selected.invoke(tc["args"])
                results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    if safe_batch:
        parallel_results = await asyncio.gather(*[
            asyncio.to_thread(s.invoke, tc["args"]) for tc, s in safe_batch
        ])
        for (tc, _), result in zip(safe_batch, parallel_results):
            results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return results


if __name__ == "__main__":
    import os
    
    THIS_FILE = os.path.abspath(__file__)  # 当前文件的绝对路径
    
    async def test_tools():
        print("=== 测试1: 直接调用工具 ===")
        result = read_file.invoke({'path': THIS_FILE})
        print(f"read_file(当前文件): {result[:100]}...")
        print(f"bash('echo hello'): {bash.invoke({'command': 'echo hello'})}")
        
        print("\n=== 测试2: 权限校验中 ===")
        print(f"plan模式调用write_file: {check_permission('write_file', {'path': 'test.txt'}, 'plan')}")
        result = check_permission('bash', {'command': 'rm -rf /tmp/test'})
        print(f"危险命令rm: {result}")
        
        print("\n=== 测试3: 模拟 tool_calls 并行执行 ===")
        tool_calls = [
            {"id": "call_1", "name": "read_file", "args": {"path": THIS_FILE}},
            {"id": "call_2", "name": "bash", "args": {"command": "ls -la"}},
        ]
        results = await execute_tools_parallel(tool_calls, mode="default")
        for r in results:
            print(f"结果: {r.content[:100]}...")
    
    asyncio.run(test_tools())