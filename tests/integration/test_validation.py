"""
Integration tests for pipeline and config validation.
"""

from __future__ import annotations

import pytest

from agentforge.core.validation import validate_pipeline_dict, validate_pipeline_yaml_string


class TestValidatePipelineDict:
    """Tests for validate_pipeline_dict."""

    def test_valid_minimal(self) -> None:
        data = {"name": "p", "steps": [{"name": "s1", "agent": "a1"}]}
        errors = validate_pipeline_dict(data)
        assert errors == []

    def test_missing_steps(self) -> None:
        data = {"name": "p"}
        errors = validate_pipeline_dict(data)
        assert any("steps" in e for e in errors)

    def test_empty_steps(self) -> None:
        data = {"name": "p", "steps": []}
        errors = validate_pipeline_dict(data)
        assert any("empty" in e.lower() for e in errors)

    def test_duplicate_step_name(self) -> None:
        data = {
            "name": "p",
            "steps": [
                {"name": "s1", "agent": "a1"},
                {"name": "s1", "agent": "a2"},
            ],
        }
        errors = validate_pipeline_dict(data)
        assert any("Duplicate" in e for e in errors)

    def test_step_missing_name(self) -> None:
        data = {"name": "p", "steps": [{"agent": "a1"}]}
        errors = validate_pipeline_dict(data)
        assert any("name" in e.lower() for e in errors)

    def test_depends_on_unknown_step(self) -> None:
        data = {
            "name": "p",
            "steps": [
                {"name": "s1", "agent": "a1"},
                {"name": "s2", "agent": "a2", "depends_on": ["nonexistent"]},
            ],
        }
        errors = validate_pipeline_dict(data)
        assert any("unknown" in e.lower() for e in errors)


class TestValidatePipelineYamlString:
    """Tests for validate_pipeline_yaml_string."""

    def test_invalid_yaml(self) -> None:
        errors = validate_pipeline_yaml_string("not: valid: yaml: [")
        assert len(errors) >= 1
        assert "YAML" in errors[0] or "dict" in errors[0]

    def test_valid_yaml(self) -> None:
        yaml_content = """
name: test
steps:
  - name: step_a
    agent: researcher
  - name: step_b
    agent: writer
    depends_on: [step_a]
"""
        errors = validate_pipeline_yaml_string(yaml_content)
        assert errors == []
