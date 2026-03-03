"""Streaming demo — watch tokens arrive in real-time with Rich formatting.

Requires the ``rich`` package (``pip install rich``).
"""

import asyncio

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from agentforge.core.agent import Agent, AgentConfig
from agentforge.llm.openai import OpenAIProvider

console = Console()


async def stream_to_console(agent: Agent, task: str) -> str:
    """Stream tokens from the agent and render them progressively."""
    buffer = ""

    console.print(Panel(task, title="Prompt", border_style="cyan"))
    console.print()

    with Live(
        Markdown(buffer),
        console=console,
        refresh_per_second=12,
        vertical_overflow="visible",
    ) as live:
        async for token in agent.stream(task):
            buffer += token
            live.update(Markdown(buffer))

    console.print()
    return buffer


async def main() -> None:
    llm = OpenAIProvider(model="gpt-4o")

    agent = Agent(
        config=AgentConfig(
            name="streamer",
            role="general",
            system_prompt=(
                "You are an expert technical writer. Respond in well-structured "
                "Markdown with headings, bullet points, and code blocks where "
                "appropriate."
            ),
            temperature=0.6,
        ),
        llm=llm,
    )

    prompts = [
        "Explain Python's GIL in 150 words, with a short code example.",
        "Give me 5 creative names for an AI coding assistant and explain each.",
    ]

    for prompt in prompts:
        await stream_to_console(agent, prompt)
        console.rule(style="dim")
        console.print()


if __name__ == "__main__":
    asyncio.run(main())
