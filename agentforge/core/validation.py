"""
Validation helpers for pipelines and config (next-level).

Validates pipeline YAML structure and step dependencies without executing.
"""

from __future__ import annotations

from typing import Any

from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Raised when pipeline or config validation fails."""

    def __init__(self, message: str, path: str | None = None) -> None:
        self.message = message
        self.path = path
        super().__init__(self.message)


def validate_pipeline_dict(data: dict[str, Any]) -> list[str]:
    """
    Validate a pipeline definition (from YAML or dict).
    Returns a list of error messages; empty list means valid.
    """
    errors: list[str] = []

    if not data or not isinstance(data, dict):
        errors.append("Pipeline must be a non-empty dict.")
        return errors

    name = data.get("name")
    if name is not None and not isinstance(name, str):
        errors.append("'name' must be a string.")

    steps = data.get("steps")
    if steps is None:
        errors.append("'steps' is required.")
        return errors
    if not isinstance(steps, list):
        errors.append("'steps' must be a list.")
        return errors
    if len(steps) == 0:
        errors.append("'steps' must not be empty.")
        return errors

    step_names: set[str] = set()
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"Step {i + 1}: must be a dict.")
            continue
        sn = step.get("name") or step.get("step")
        if not sn:
            errors.append(f"Step {i + 1}: missing 'name'.")
        elif not isinstance(sn, str):
            errors.append(f"Step {i + 1}: 'name' must be a string.")
        elif sn in step_names:
            errors.append(f"Duplicate step name: {sn!r}.")
        else:
            step_names.add(sn)

        agent = step.get("agent") or step.get("agent_name")
        if agent is not None and not isinstance(agent, str):
            errors.append(f"Step {sn or i + 1}: 'agent' must be a string.")

        input_map = step.get("input_map")
        if input_map is not None and not isinstance(input_map, dict):
            errors.append(f"Step {sn or i + 1}: 'input_map' must be a dict.")

        depends_on = step.get("depends_on")
        if depends_on is not None and not isinstance(depends_on, list):
            errors.append(f"Step {sn or i + 1}: 'depends_on' must be a list.")

    # Check that depends_on and input_map reference only existing steps
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        sn = step.get("name") or step.get("step") or str(i)
        for dep in step.get("depends_on") or []:
            if dep not in step_names:
                errors.append(f"Step {sn!r}: depends_on references unknown step {dep!r}.")
        for _param, source in (step.get("input_map") or {}).items():
            if source not in step_names and source != "__task__":
                errors.append(f"Step {sn!r}: input_map references unknown step {source!r}.")

    return errors


def validate_pipeline_yaml_string(yaml_content: str) -> list[str]:
    """Load YAML and validate pipeline. Returns list of errors."""
    try:
        import yaml
        data = yaml.safe_load(yaml_content)
    except Exception as e:
        return [f"Invalid YAML: {e}"]
    return validate_pipeline_dict(data) if isinstance(data, dict) else ["YAML root must be a dict."]
