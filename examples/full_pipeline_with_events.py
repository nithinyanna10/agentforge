"""
Full example: run a pipeline with event bus subscription and middleware (next-level).

This example shows how to:
- Validate pipeline YAML
- Subscribe to pipeline events
- Add truncation middleware
- Run a pipeline (if orchestrator and agents are configured)

Run from repo root:
  python -m examples.full_pipeline_with_events

Requires: agentforge installed or PYTHONPATH including the package.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentforge.core.validation import validate_pipeline_dict, validate_pipeline_yaml_string
from agentforge.core.pipeline_events import (
    get_pipeline_event_bus,
    PipelineEvent,
    PipelineEventType,
    truncate_context_middleware,
    logging_middleware,
)


def load_example_pipeline() -> dict:
    """Load the summarize_doc pipeline as dict."""
    workflows_dir = Path(__file__).resolve().parent.parent / "workflows"
    path = workflows_dir / "summarize_doc.yaml"
    if not path.exists():
        return {"name": "example", "steps": [{"name": "s1", "agent": "researcher"}]}
    import yaml
    return yaml.safe_load(path.read_text())


def main_sync() -> None:
    """Synchronous part: validate and show events."""
    data = load_example_pipeline()
    errors = validate_pipeline_dict(data)
    if errors:
        print("Validation errors:", errors)
        return
    print("Pipeline valid:", data.get("name"), "steps:", len(data.get("steps", [])))

    bus = get_pipeline_event_bus()
    events_log: list[str] = []

    def collector(event: PipelineEvent) -> None:
        events_log.append(f"{event.type.value}: {event.step_name or event.pipeline_name}")

    bus.subscribe(collector)
    # In a real run, the orchestrator would emit events; here we emit one manually for demo
    async def emit_one() -> None:
        await bus.emit(
            PipelineEvent(
                type=PipelineEventType.STEP_START,
                pipeline_name=data.get("name", ""),
                step_name="fetch",
            )
        )

    asyncio.run(emit_one())
    print("Events received:", events_log)

    # Add middleware (for when pipeline actually runs)
    bus.add_middleware(logging_middleware)
    bus.add_middleware(lambda sn, ctx: truncate_context_middleware(sn, ctx, max_value_chars=2000))
    print("Middleware registered. Run orchestrator.run_pipeline() to see them in action.")


if __name__ == "__main__":
    main_sync()
