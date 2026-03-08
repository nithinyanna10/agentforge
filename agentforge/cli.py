"""AgentForge CLI — beautiful terminal interface powered by Typer + Rich."""

from __future__ import annotations

import asyncio
import importlib.metadata
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.status import Status
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# ---------------------------------------------------------------------------
# Theme & console
# ---------------------------------------------------------------------------

_THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "agent": "bold magenta",
        "tool": "bold blue",
        "step": "bold white",
    }
)

console = Console(theme=_THEME)

# ---------------------------------------------------------------------------
# Typer app
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="agentforge",
    help="🔥 AgentForge — production-ready multi-agent orchestration framework",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _version_string() -> str:
    try:
        return importlib.metadata.version("agentforge")
    except importlib.metadata.PackageNotFoundError:
        return "0.1.0-dev"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_thinking(text: str) -> Panel:
    return Panel(
        Text(text, style="dim italic"),
        title="[agent]💭 Thinking[/agent]",
        border_style="magenta",
        padding=(1, 2),
    )


def _render_tool_call(tool_name: str, args: dict) -> Panel:
    arg_lines = yaml.dump(args, default_flow_style=False).strip() if args else ""
    body = Syntax(arg_lines, "yaml", theme="monokai", line_numbers=False)
    return Panel(
        body,
        title=f"[tool]🔧 Tool Call → {tool_name}[/tool]",
        border_style="blue",
        padding=(1, 2),
    )


def _render_result(content: str) -> Panel:
    try:
        md = Markdown(content)
    except Exception:
        md = Text(content)
    return Panel(
        md,
        title="[success]✅ Result[/success]",
        border_style="green",
        padding=(1, 2),
    )


def _render_error(message: str) -> Panel:
    return Panel(
        Text(message, style="error"),
        title="[error]❌ Error[/error]",
        border_style="red",
        padding=(1, 2),
    )


def _render_code_block(code: str, language: str = "python") -> Syntax:
    return Syntax(code, language, theme="monokai", line_numbers=True, padding=1)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command()
def run(
    task: Annotated[str, typer.Argument(help="The task to execute")],
    agent: Annotated[
        Optional[str],
        typer.Option("--agent", "-a", help="Agent name to use"),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="LLM model identifier"),
    ] = None,
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", "-p", help="LLM provider (openai, anthropic, …)"),
    ] = None,
) -> None:
    """Run a task with a single agent interactively."""

    agent_label = agent or "default"
    model_label = model or "auto"
    provider_label = provider or "auto"

    header = Table.grid(padding=(0, 2))
    header.add_column(style="bold")
    header.add_column()
    header.add_row("Agent", f"[agent]{agent_label}[/agent]")
    header.add_row("Model", f"[info]{model_label}[/info]")
    header.add_row("Provider", f"[info]{provider_label}[/info]")

    console.print()
    console.print(
        Panel(
            header,
            title="[bold]🚀 AgentForge — Run[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()

    console.print(
        Panel(
            Text(task, style="bold white"),
            title="[step]📝 Task[/step]",
            border_style="white",
            padding=(1, 2),
        )
    )
    console.print()

    async def _execute() -> None:
        from agentforge.core.agent import Agent  # type: ignore[import-untyped]
        from agentforge.core.config import AgentConfig  # type: ignore[import-untyped]

        config = AgentConfig(
            name=agent_label,
            model=model_label,
            provider=provider_label,
        )
        ag = Agent(config=config)

        with Status("[agent]Agent is thinking…[/agent]", console=console, spinner="dots"):
            result = await ag.run(task)

        for event in result.events:
            match event.type:
                case "thinking":
                    console.print(_render_thinking(event.content))
                case "tool_call":
                    console.print(_render_tool_call(event.tool_name, event.tool_args))
                case "tool_result":
                    console.print(_render_result(event.content))
                case "error":
                    console.print(_render_error(event.content))
                case "code":
                    console.print(_render_code_block(event.content, event.language))
            console.print()

        console.print(
            Panel(
                Markdown(result.final_answer),
                title="[success]🏁 Final Answer[/success]",
                border_style="green",
                padding=(1, 2),
            )
        )

    try:
        asyncio.run(_execute())
    except KeyboardInterrupt:
        console.print("\n[warning]Interrupted by user.[/warning]")
        raise typer.Exit(code=130)
    except Exception as exc:
        console.print(_render_error(str(exc)))
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------


@app.command()
def pipeline(
    yaml_path: Annotated[
        Path,
        typer.Argument(
            help="Path to a pipeline YAML configuration file",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Run a multi-step pipeline defined in a YAML file."""

    console.print()
    console.print(
        Panel(
            f"[info]{yaml_path}[/info]",
            title="[bold]⚙️  AgentForge — Pipeline[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()

    with open(yaml_path) as fh:
        pipeline_def = yaml.safe_load(fh)

    steps: list[dict] = pipeline_def.get("steps", [])
    if not steps:
        console.print(_render_error("No steps found in pipeline YAML."))
        raise typer.Exit(code=1)

    step_table = Table(title="Pipeline Steps", border_style="cyan", show_lines=True)
    step_table.add_column("#", justify="right", style="bold", width=4)
    step_table.add_column("Name", style="agent")
    step_table.add_column("Agent", style="info")
    step_table.add_column("Description", style="dim")

    for idx, step in enumerate(steps, 1):
        step_table.add_row(
            str(idx),
            step.get("name", "—"),
            step.get("agent", "default"),
            step.get("description", ""),
        )

    console.print(step_table)
    console.print()

    async def _run_pipeline() -> None:
        from agentforge.core.pipeline import Pipeline  # type: ignore[import-untyped]

        pipe = Pipeline.from_dict(pipeline_def)

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        )

        with progress:
            task_id = progress.add_task("Running pipeline…", total=len(steps))

            async for event in pipe.execute_stream():
                match event.type:
                    case "step_start":
                        progress.update(
                            task_id,
                            description=f"[step]▶ {event.step_name}[/step]",
                        )
                    case "step_complete":
                        progress.advance(task_id)
                        console.print(
                            f"  [success]✓[/success] {event.step_name} completed"
                        )
                    case "thinking":
                        console.print(_render_thinking(event.content))
                    case "tool_call":
                        console.print(
                            _render_tool_call(event.tool_name, event.tool_args)
                        )
                    case "result":
                        console.print(_render_result(event.content))
                    case "error":
                        console.print(_render_error(event.content))

        console.print()
        console.print("[success]Pipeline finished.[/success]")

    try:
        asyncio.run(_run_pipeline())
    except KeyboardInterrupt:
        console.print("\n[warning]Interrupted by user.[/warning]")
        raise typer.Exit(code=130)
    except Exception as exc:
        console.print(_render_error(str(exc)))
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Bind address"),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Bind port"),
    ] = 8000,
) -> None:
    """Start the AgentForge FastAPI server."""

    import uvicorn

    console.print()
    console.print(
        Panel(
            Columns(
                [
                    Text(f"Host: {host}", style="info"),
                    Text(f"Port: {port}", style="info"),
                ],
                padding=(0, 4),
            ),
            title="[bold]🌐 AgentForge — Server[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()

    uvicorn.run(
        "agentforge.server.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------


@app.command()
def tools() -> None:
    """List all available tools (built-in and registered extensions)."""

    from agentforge.ext import get_registered_tools

    registry = get_registered_tools()

    table = Table(
        title="🧰 Available Tools",
        border_style="blue",
        show_lines=True,
        padding=(0, 2),
    )
    table.add_column("Tool", style="tool", min_width=20)
    table.add_column("Description", style="dim")
    table.add_column("Version", justify="center", style="info")

    for tool_cls in sorted(registry, key=lambda t: t.__name__):
        try:
            inst = tool_cls()
            name = inst.name
            desc = inst.description
        except Exception:
            name = getattr(tool_cls, "__name__", "Tool")
            desc = "Custom or configured tool (init requires arguments)"
        table.add_row(
            name,
            desc[:80] + "…" if len(desc) > 80 else desc,
            getattr(tool_cls, "version", "—"),
        )

    console.print()
    console.print(table)
    console.print()
    console.print(f"[dim]{len(registry)} tool(s) registered[/dim]")


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Show the AgentForge version."""

    ver = _version_string()
    banner = Text.assemble(
        ("AgentForge ", "bold magenta"),
        (f"v{ver}", "bold cyan"),
    )
    console.print()
    console.print(Panel(banner, border_style="magenta", padding=(1, 4)))
