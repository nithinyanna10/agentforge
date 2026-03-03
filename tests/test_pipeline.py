"""Tests for agentforge.core.pipeline.Pipeline and PipelineStep."""

from __future__ import annotations

import textwrap

import pytest

from agentforge.core.pipeline import Pipeline, PipelineStep


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pipeline_add_steps():
    pipe = Pipeline(name="p")
    pipe.add_step(PipelineStep(name="a", agent_name="agent_a"))
    pipe.add_step(PipelineStep(name="b", agent_name="agent_b"))

    assert len(pipe) == 2
    assert [s.name for s in pipe.steps] == ["a", "b"]


def test_pipeline_add_duplicate_raises():
    pipe = Pipeline(name="p")
    pipe.add_step(PipelineStep(name="a", agent_name="agent_a"))

    with pytest.raises(ValueError, match="Duplicate step name"):
        pipe.add_step(PipelineStep(name="a", agent_name="agent_a"))


def test_pipeline_resolve_linear():
    """A -> B -> C resolves into 3 sequential layers."""
    pipe = Pipeline(name="linear", steps=[
        PipelineStep(name="A", agent_name="a"),
        PipelineStep(name="B", agent_name="b", depends_on=["A"]),
        PipelineStep(name="C", agent_name="c", depends_on=["B"]),
    ])

    layers = pipe.resolve()

    assert len(layers) == 3
    assert [layers[0][0].name] == ["A"]
    assert [layers[1][0].name] == ["B"]
    assert [layers[2][0].name] == ["C"]


def test_pipeline_resolve_parallel():
    """A and B have no deps so they share layer 1; C depends on both."""
    pipe = Pipeline(name="par", steps=[
        PipelineStep(name="A", agent_name="a"),
        PipelineStep(name="B", agent_name="b"),
        PipelineStep(name="C", agent_name="c", depends_on=["A", "B"]),
    ])

    layers = pipe.resolve()

    assert len(layers) == 2
    first_layer_names = {s.name for s in layers[0]}
    assert first_layer_names == {"A", "B"}
    assert layers[1][0].name == "C"


def test_pipeline_cycle_detection():
    """Cyclic dependencies must raise ValueError."""
    pipe = Pipeline(name="cycle", steps=[
        PipelineStep(name="A", agent_name="a", depends_on=["B"]),
        PipelineStep(name="B", agent_name="b", depends_on=["A"]),
    ])

    with pytest.raises(ValueError, match="cycle"):
        pipe.resolve()


def test_pipeline_unknown_dep_raises():
    pipe = Pipeline(name="bad", steps=[
        PipelineStep(name="A", agent_name="a", depends_on=["Z"]),
    ])

    with pytest.raises(ValueError, match="unknown step"):
        pipe.resolve()


def test_pipeline_from_yaml(tmp_path):
    yaml_content = textwrap.dedent("""\
        name: my_pipeline
        steps:
          - name: research
            agent: researcher
            input_map: {}
            depends_on: []
          - name: write
            agent: writer
            input_map:
              context: research
            depends_on:
              - research
          - name: review
            agent: reviewer
            depends_on:
              - write
    """)
    yaml_file = tmp_path / "pipeline.yaml"
    yaml_file.write_text(yaml_content)

    pipe = Pipeline.from_yaml(yaml_file)

    assert pipe.name == "my_pipeline"
    assert len(pipe) == 3
    names = [s.name for s in pipe.steps]
    assert names == ["research", "write", "review"]

    layers = pipe.resolve()
    assert len(layers) == 3


def test_pipeline_step_condition():
    """Steps whose condition returns False are effectively no-ops at resolve time.

    The condition is evaluated at *run* time by the orchestrator, but we
    verify the callable is stored correctly and ``effective_deps`` works.
    """
    always_false = lambda ctx: False
    step = PipelineStep(
        name="maybe",
        agent_name="a",
        condition=always_false,
        depends_on=["prior"],
    )

    assert step.condition is not None
    assert step.condition({}) is False
    assert "prior" in step.effective_deps()


def test_pipeline_to_dict():
    pipe = Pipeline(name="ser", steps=[
        PipelineStep(name="A", agent_name="a"),
        PipelineStep(name="B", agent_name="b", depends_on=["A"]),
    ])

    d = pipe.to_dict()

    assert d["name"] == "ser"
    assert len(d["steps"]) == 2
    assert d["steps"][1]["depends_on"] == ["A"]
