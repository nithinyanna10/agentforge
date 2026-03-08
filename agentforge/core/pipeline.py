"""Pipeline — a directed acyclic graph of execution steps."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PipelineStep(BaseModel):
    """A single node in the pipeline DAG.

    Attributes:
        name:        Unique identifier for this step.
        agent_name:  The registered agent that will execute this step.
        input_map:   Maps local parameter names to the output keys of
                     upstream steps (``{"context": "step_a"}`` means this
                     step receives the answer of *step_a* as *context*).
        depends_on:  Explicit list of upstream step names that must complete
                     before this step starts.  Inferred from *input_map*
                     when omitted.
        condition:   Optional callable ``(context: dict) -> bool``.  If it
                     returns ``False`` the step is skipped at runtime.
    """

    name: str
    agent_name: str
    input_map: dict[str, str] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    condition: Callable[[dict[str, Any]], bool] | None = Field(default=None, exclude=True)
    retries: int = Field(default=0, ge=0, le=10)
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)

    model_config = {"arbitrary_types_allowed": True}

    def effective_deps(self) -> set[str]:
        """Return the union of explicit deps and those implied by *input_map*."""
        return set(self.depends_on) | set(self.input_map.values())


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    """An ordered collection of ``PipelineStep`` nodes with dependency resolution.

    Steps that share no dependencies are scheduled together in the same layer
    so the orchestrator can run them concurrently.
    """

    def __init__(self, name: str, steps: list[PipelineStep] | None = None) -> None:
        self.name = name
        self._steps: dict[str, PipelineStep] = {}
        for step in steps or []:
            self.add_step(step)

    # -- mutators ------------------------------------------------------------

    def add_step(self, step: PipelineStep) -> Pipeline:
        """Append a step and return ``self`` for chaining."""
        if step.name in self._steps:
            raise ValueError(f"Duplicate step name: {step.name!r}")
        self._steps[step.name] = step
        return self

    # -- dependency resolution -----------------------------------------------

    def resolve(self) -> list[list[PipelineStep]]:
        """Return steps grouped into layers via Kahn's algorithm.

        Each inner list is a set of steps whose dependencies are fully
        satisfied by prior layers — they can run in parallel.

        Raises ``ValueError`` if the graph contains a cycle.
        """
        in_degree: dict[str, int] = {name: 0 for name in self._steps}
        dependents: dict[str, list[str]] = {name: [] for name in self._steps}

        for name, step in self._steps.items():
            for dep in step.effective_deps():
                if dep not in self._steps:
                    raise ValueError(f"Step {name!r} depends on unknown step {dep!r}")
                in_degree[name] += 1
                dependents[dep].append(name)

        queue = [name for name, deg in in_degree.items() if deg == 0]
        layers: list[list[PipelineStep]] = []
        visited = 0

        while queue:
            layer = [self._steps[n] for n in queue]
            layers.append(layer)
            next_queue: list[str] = []
            for name in queue:
                visited += 1
                for child in dependents[name]:
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        next_queue.append(child)
            queue = next_queue

        if visited != len(self._steps):
            raise ValueError("Pipeline contains a dependency cycle")

        return layers

    # -- serialisation helpers -----------------------------------------------

    @classmethod
    def from_yaml(cls, path: str | Path) -> Pipeline:
        """Load a pipeline definition from a YAML file.

        Expected schema::

            name: my_pipeline
            steps:
              - name: step_a
                agent: researcher
                input_map: {}
                depends_on: []
              - name: step_b
                agent: writer
                input_map:
                  context: step_a
                depends_on:
                  - step_a
        """
        import yaml  # lazily imported so PyYAML is only needed when loading YAML

        raw = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(raw)

        pipeline_name: str = data.get("name", Path(path).stem)
        steps: list[PipelineStep] = []
        for entry in data.get("steps", []):
            steps.append(
                PipelineStep(
                    name=entry["name"],
                    agent_name=entry.get("agent", entry.get("agent_name", "")),
                    input_map=entry.get("input_map", {}),
                    depends_on=entry.get("depends_on", []),
                    retries=entry.get("retries", 0),
                    timeout_seconds=entry.get("timeout_seconds"),
                )
            )
        logger.info("Loaded pipeline %r with %d steps from %s", pipeline_name, len(steps), path)
        return cls(name=pipeline_name, steps=steps)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the pipeline to a plain dict (suitable for JSON/YAML)."""
        return {
            "name": self.name,
            "steps": [
                {
                    "name": s.name,
                    "agent": s.agent_name,
                    "input_map": s.input_map,
                    "depends_on": s.depends_on,
                    "retries": s.retries,
                    "timeout_seconds": s.timeout_seconds,
                }
                for s in self._steps.values()
            ],
        }

    # -- dunder --------------------------------------------------------------

    @property
    def steps(self) -> list[PipelineStep]:
        return list(self._steps.values())

    def __len__(self) -> int:
        return len(self._steps)

    def __repr__(self) -> str:
        return f"Pipeline(name={self.name!r}, steps={len(self._steps)})"
