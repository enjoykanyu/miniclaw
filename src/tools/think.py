from langchain_core.tools import tool


@tool
def think(thought: str) -> str:
    """Use this tool to think through complex problems step by step before responding."""
    return f"Thinking: {thought}"
