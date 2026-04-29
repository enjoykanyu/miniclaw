"""
MiniClaw CLI Interface
Provides command-line interface for interacting with MiniClaw
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from miniclaw.core.graph import MiniClawApp
from miniclaw.utils.helpers import init_data_dirs
from miniclaw.config.settings import settings
from miniclaw.tools.scheduler import setup_default_reminders

app = typer.Typer(
    name="miniclaw",
    help="MiniClaw - Personal AI Assistant based on LangGraph and LangChain",
    add_completion=False,
)

console = Console()


@app.command()
def chat(
    message: str = typer.Argument(..., help="Message to send to MiniClaw"),
    user_id: str = typer.Option("default", "--user", "-u", help="User ID"),
):
    """Send a message to MiniClaw and get a response."""
    init_data_dirs()
    
    async def run_chat():
        try:
            app_instance = MiniClawApp()
            response = await app_instance.chat(
                message=message,
                user_id=user_id,
            )
            return response
        except Exception as e:
            return f"Error: {str(e)}"
    
    response = asyncio.run(run_chat())
    
    console.print(Panel(response, title="MiniClaw", border_style="blue"))


@app.command()
def interactive(
    user_id: str = typer.Option("default", "--user", "-u", help="User ID"),
):
    """Start an interactive chat session with MiniClaw."""
    init_data_dirs()
    
    # ASCII Art Banner
    banner = """
[bold cyan]    __  __ _       _      _                 [/bold cyan]
[bold cyan]   |  \/  (_)     (_)    | |                [/bold cyan]
[bold cyan]   | .  . |_ _ __  _  ___| | __             [/bold cyan]
[bold cyan]   | |\/| | | '_ \| |/ __| |/ /             [/bold cyan]
[bold cyan]   | |  | | | | | | | (__|   <              [/bold cyan]
[bold cyan]   \_|  |_/_|_| |_|_|\___|_|\_\             [/bold cyan]
[bold cyan]                                            [/bold cyan]
[bold green]   🤖 Personal AI Assistant[/bold green]               
[dim]   Type 'exit' or 'quit' to end session[/dim]
    """
    console.print(banner)
    
    app_instance = MiniClawApp()
    session_id = "cli_session"
    
    while True:
        user_input = Prompt.ask("[bold green]You[/bold green]")
        
        if user_input.lower() in ["exit", "quit", "q"]:
            console.print("[yellow]Goodbye![/yellow]")
            break
        
        if not user_input.strip():
            continue
        
        try:
            # 使用流式输出
            console.print("[bold blue]MiniClaw:[/bold blue] ", end="")
            
            async def stream_response():
                async for event in app_instance.stream(
                    message=user_input,
                    user_id=user_id,
                    session_id=session_id,
                ):
                    # 处理 astream_events 返回的事件
                    if isinstance(event, dict):
                        event_type = event.get("event")
                        # 只处理聊天模型的流式输出
                        if event_type == "on_chat_model_stream":
                            data = event.get("data", {})
                            chunk = data.get("chunk", {})
                            if hasattr(chunk, "content"):
                                content = chunk.content
                                if content:
                                    console.print(content, end="")
                            elif isinstance(chunk, dict):
                                content = chunk.get("content", "")
                                if content:
                                    console.print(content, end="")
                console.print()  # 换行
            
            asyncio.run(stream_response())
            
        except Exception as e:
            console.print(f"\n[red]Error: {str(e)}[/red]")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(9190, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
):
    """Start the FastAPI server."""
    init_data_dirs()
    
    import uvicorn
    from miniclaw.api import app as fastapi_app
    
    console.print(Panel.fit(
        f"[bold green]Starting MiniClaw API Server[/bold green]\n"
        f"Server: http://{host}:{port}",
        border_style="blue",
    ))
    
    uvicorn.run(
        "miniclaw.api:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def init():
    """Initialize MiniClaw directories and configuration."""
    init_data_dirs()
    console.print("[green]✓[/green] Initialized MiniClaw directories")


@app.command()
def config():
    """Show current configuration."""
    console.print(Panel.fit(
        f"[bold]LLM Provider:[/bold] {settings.LLM_PROVIDER}\n"
        f"[bold]Model:[/bold] {getattr(settings, f'{settings.LLM_PROVIDER.upper()}_MODEL', 'N/A')}\n"
        f"[bold]Default City:[/bold] {settings.DEFAULT_CITY}\n"
        f"[bold]Data Dir:[/bold] {settings.DATA_DIR}\n"
        f"[bold]Log Level:[/bold] {settings.LOG_LEVEL}",
        title="Configuration",
        border_style="green",
    ))


@app.command()
def test_llm():
    """Test LLM connection."""
    from miniclaw.utils.llm import get_llm
    
    console.print("[yellow]Testing LLM connection...[/yellow]")
    
    try:
        llm = get_llm()
        
        async def test():
            response = await llm.ainvoke("Hello, say hi in Chinese")
            return response
        
        response = asyncio.run(test())
        console.print(f"[green]✓[/green] LLM Response: {response.content}")
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {str(e)}")


if __name__ == "__main__":
    app()
