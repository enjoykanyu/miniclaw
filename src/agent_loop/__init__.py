"""
Agentic Loop — 对标 OpenClaw 的 Agent Loop 推理循环

三层嵌套架构：
  - 主循环层 (runEmbeddedPiAgent): while(true) 重试/恢复
  - 尝试层 (runEmbeddedAttempt): 单次推理生命周期
  - 事件层 (subscribeEmbeddedPiSession): 流式响应处理

LangGraph 实现：
  - StateGraph + 条件边实现循环控制
  - agent_reason ↔ tool_execute 实现 ReAct 循环
  - supervisor 实现多 Agent 协作路由
  - compaction 实现上下文压缩
  - loop_detection 实现循环检测与断路器
"""

from agent_loop.state import AgenticLoopState, create_loop_state, LoopPhase, AttemptStatus
from agent_loop.app import AgenticLoopApp
from agent_loop.graph import build_agentic_loop_graph
from agent_loop.loop_detection import LoopDetector, IdleTimeoutBreaker, PostCompactionLoopGuard

__all__ = [
    "AgenticLoopState",
    "create_loop_state",
    "LoopPhase",
    "AttemptStatus",
    "AgenticLoopApp",
    "build_agentic_loop_graph",
    "LoopDetector",
    "IdleTimeoutBreaker",
    "PostCompactionLoopGuard",
]
