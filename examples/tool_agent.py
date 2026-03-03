"""Agent with tools — demonstrates web search, code execution, and event hooks.

The agent can search the web and run Python code to answer complex questions
that require gathering information and then acting on it.
"""

import asyncio

from agentforge.core.agent import Agent, AgentConfig, AgentResult, ToolCallRecord
from agentforge.llm.openai import OpenAIProvider
from agentforge.tools.code_executor import CodeExecutorTool
from agentforge.tools.web_search import WebSearchTool


def on_thinking(agent_name: str, thought: str) -> None:
    """Print the agent's internal reasoning as it happens."""
    preview = thought[:120].replace("\n", " ")
    print(f"  💭 [{agent_name}] {preview}{'…' if len(thought) > 120 else ''}")


def on_tool_call(agent_name: str, record: ToolCallRecord) -> None:
    """Print each tool invocation and its outcome."""
    status = "✅" if record.result and record.result.success else "❌"
    print(f"  🔧 [{agent_name}] {record.tool_name}({record.arguments}) → {status}")
    if record.result and record.result.output:
        for line in record.result.output.strip().splitlines()[:5]:
            print(f"       {line}")


def on_result(agent_name: str, result: AgentResult) -> None:
    """Print a summary once the agent finishes."""
    print(f"\n  📋 [{agent_name}] Done — {len(result.tool_calls)} tool call(s), "
          f"{len(result.thinking_steps)} thinking step(s), "
          f"{result.duration_seconds:.2f}s")


async def main() -> None:
    llm = OpenAIProvider(model="gpt-4o")
    tools = [WebSearchTool(), CodeExecutorTool()]

    agent = Agent(
        config=AgentConfig(
            name="researcher",
            role="research",
            system_prompt=(
                "You are a research agent. Use web_search to find information and "
                "code_executor to run Python scripts when needed. Always verify "
                "facts before presenting them."
            ),
            max_react_steps=6,
        ),
        llm=llm,
        tools=tools,
    )

    agent.on_thinking = on_thinking
    agent.on_tool_call = on_tool_call
    agent.on_result = on_result

    task = (
        "Search for the latest stable Python release version, then write "
        "and execute a short Python script that prints that version number."
    )

    print(f"Task: {task}\n")
    result = await agent.run(task)
    print(f"\nFinal answer:\n{result.answer}")


if __name__ == "__main__":
    asyncio.run(main())
