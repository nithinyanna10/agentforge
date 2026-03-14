"""
Next-level demo: use new tools, pipeline events, and validation.

Run from repo root:
  python -m examples.next_level_demo

Requires: agentforge installed or PYTHONPATH including the package.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentforge.tools.summarize import SummarizeTool
from agentforge.tools.json_path import JSONPathTool
from agentforge.tools.regex_tool import RegexTool
from agentforge.core.pipeline_events import get_pipeline_event_bus, PipelineEvent, PipelineEventType
from agentforge.core.validation import validate_pipeline_dict


async def demo_summarize() -> None:
    print("--- SummarizeTool ---")
    tool = SummarizeTool()
    text = "First sentence. Second sentence. Third sentence. Fourth. Fifth. Sixth."
    result = await tool.execute(text=text, strategy="sentences", max_sentences=3)
    print(f"Success: {result.success}, Output: {result.output[:80]}...")


async def demo_json_path() -> None:
    print("--- JSONPathTool ---")
    tool = JSONPathTool()
    data = '{"user": {"name": "Alice", "roles": ["admin", "user"]}}'
    result = await tool.execute(json_text=data, path="$.user.name")
    print(f"Success: {result.success}, Output: {result.output}")


async def demo_regex() -> None:
    print("--- RegexTool ---")
    tool = RegexTool()
    text = "Contact: alice@example.com and bob@test.org"
    result = await tool.execute(text=text, pattern=r"[\w.-]+@[\w.-]+\.\w+", mode="find")
    print(f"Success: {result.success}, Output: {result.output}")


def demo_validation() -> None:
    print("--- Pipeline validation ---")
    valid = {"name": "demo", "steps": [{"name": "s1", "agent": "researcher"}]}
    errors = validate_pipeline_dict(valid)
    print(f"Valid pipeline: errors = {errors}")

    invalid = {"name": "demo", "steps": [{"name": "s1"}, {"name": "s1", "agent": "a"}]}
    errors = validate_pipeline_dict(invalid)
    print(f"Invalid (duplicate name): errors = {errors}")


async def demo_event_bus() -> None:
    print("--- Pipeline event bus ---")
    bus = get_pipeline_event_bus()
    events_received: list[str] = []
    bus.subscribe(lambda e: events_received.append(e.type.value))
    await bus.emit(PipelineEvent(type=PipelineEventType.STEP_START, step_name="demo_step"))
    print(f"Received events: {events_received}")


async def main() -> None:
    await demo_summarize()
    await demo_json_path()
    await demo_regex()
    demo_validation()
    await demo_event_bus()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
