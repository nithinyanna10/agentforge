"""Simple single-agent example — ask a question and get an answer."""

import asyncio

from agentforge.core.agent import Agent, AgentConfig
from agentforge.llm.openai import OpenAIProvider


async def main() -> None:
    llm = OpenAIProvider(model="gpt-4o")
    agent = Agent(
        config=AgentConfig(
            name="assistant",
            role="general",
            system_prompt="You are a helpful and concise AI assistant.",
        ),
        llm=llm,
    )

    result = await agent.run("What are the top 3 benefits of using async/await in Python?")
    print(f"Answer: {result.answer}")
    print(f"Duration: {result.duration_seconds:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
