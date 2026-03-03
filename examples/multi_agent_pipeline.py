"""Multi-agent pipeline — three agents collaborate through an orchestrator.

This example creates a research → write → review pipeline where each agent's
output feeds into the next stage automatically.
"""

import asyncio

from agentforge.core.agent import Agent, AgentConfig
from agentforge.core.orchestrator import Orchestrator
from agentforge.core.pipeline import Pipeline, PipelineStep
from agentforge.llm.openai import OpenAIProvider


def build_agents(llm: OpenAIProvider) -> list[Agent]:
    """Create the three specialised agents used in the pipeline."""
    researcher = Agent(
        config=AgentConfig(
            name="researcher",
            role="research",
            system_prompt=(
                "You are a research specialist. Gather key facts, statistics, "
                "and insights on the given topic. Output a concise research brief."
            ),
            temperature=0.4,
        ),
        llm=llm,
    )

    writer = Agent(
        config=AgentConfig(
            name="writer",
            role="writing",
            system_prompt=(
                "You are a skilled technical writer. Using the provided research "
                "and outline, produce a clear, engaging article of roughly 300 words."
            ),
            temperature=0.7,
        ),
        llm=llm,
    )

    reviewer = Agent(
        config=AgentConfig(
            name="reviewer",
            role="review",
            system_prompt=(
                "You are an editor. Review the draft for factual accuracy, "
                "clarity, and grammar. Output the final polished version with "
                "a brief summary of changes at the end."
            ),
            temperature=0.3,
        ),
        llm=llm,
    )

    return [researcher, writer, reviewer]


def build_pipeline() -> Pipeline:
    """Define a three-step sequential pipeline."""
    return Pipeline(
        name="research_write_review",
        steps=[
            PipelineStep(
                name="research",
                agent_name="researcher",
                input_map={},
                depends_on=[],
            ),
            PipelineStep(
                name="write",
                agent_name="writer",
                input_map={"research_findings": "research"},
                depends_on=["research"],
            ),
            PipelineStep(
                name="review",
                agent_name="reviewer",
                input_map={"draft": "write"},
                depends_on=["write"],
            ),
        ],
    )


async def main() -> None:
    llm = OpenAIProvider(model="gpt-4o")

    orchestrator = Orchestrator()
    for agent in build_agents(llm):
        orchestrator.register(agent)

    pipeline = build_pipeline()

    result = await orchestrator.run_pipeline(
        pipeline,
        initial_inputs={"__task__": "The impact of WebAssembly on modern web development"},
    )

    print("=" * 60)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Execution order: {' → '.join(result.execution_order)}\n")

    for step_name, agent_result in result.results.items():
        print(f"--- {step_name.upper()} ({agent_result.duration_seconds:.2f}s) ---")
        print(agent_result.answer[:300])
        if len(agent_result.answer) > 300:
            print("  …(truncated)")
        print()

    print("=" * 60)
    print("FINAL OUTPUT")
    print("=" * 60)
    print(result.merged_answer)


if __name__ == "__main__":
    asyncio.run(main())
