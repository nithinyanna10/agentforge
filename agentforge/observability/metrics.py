"""In-process metrics registry compatible with Prometheus exposition format."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


class MetricType(StrEnum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class MetricSample(BaseModel):
    name: str
    labels: dict[str, str] = Field(default_factory=dict)
    value: float = 0.0
    timestamp: datetime | None = None


class Counter:
    def __init__(self, name: str, help_text: str, label_names: list[str]) -> None:
        self._name = name
        self._help = help_text
        self._labels = label_names
        self._values: dict[tuple, float] = defaultdict(float)

    def inc(self, labels: dict[str, str] | None = None, amount: float = 1.0) -> None:
        key = tuple((labels or {}).get(k, "") for k in self._labels)
        self._values[key] += amount

    def get(self, labels: dict[str, str] | None = None) -> float:
        key = tuple((labels or {}).get(k, "") for k in self._labels)
        return self._values[key]


class Gauge:
    def __init__(self, name: str, help_text: str, label_names: list[str]) -> None:
        self._name = name
        self._help = help_text
        self._labels = label_names
        self._values: dict[tuple, float] = defaultdict(float)

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = tuple((labels or {}).get(k, "") for k in self._labels)
        self._values[key] = value

    def inc(self, labels: dict[str, str] | None = None, amount: float = 1.0) -> None:
        key = tuple((labels or {}).get(k, "") for k in self._labels)
        self._values[key] += amount

    def dec(self, labels: dict[str, str] | None = None, amount: float = 1.0) -> None:
        self.inc(labels=labels, amount=-amount)

    def get(self, labels: dict[str, str] | None = None) -> float:
        key = tuple((labels or {}).get(k, "") for k in self._labels)
        return self._values[key]


class Histogram:
    def __init__(self, name: str, help_text: str, label_names: list[str], max_observations: int = 10000) -> None:
        self._name = name
        self._help = help_text
        self._labels = label_names
        self._max = max_observations
        self._values: dict[tuple, list[float]] = defaultdict(list)

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = tuple((labels or {}).get(k, "") for k in self._labels)
        lst = self._values[key]
        lst.append(value)
        if len(lst) > self._max:
            lst.pop(0)

    def get_stats(self, labels: dict[str, str] | None = None) -> dict[str, float]:
        key = tuple((labels or {}).get(k, "") for k in self._labels)
        lst = sorted(self._values[key])
        n = len(lst)
        if n == 0:
            return {"count": 0, "sum": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
        return {
            "count": n,
            "sum": sum(lst),
            "avg": sum(lst) / n,
            "p50": lst[int(n * 0.5)] if n else 0,
            "p95": lst[int(n * 0.95)] if n > 1 else lst[0],
            "p99": lst[int(n * 0.99)] if n > 1 else lst[0],
        }


_metrics: "Metrics | None" = None


class Metrics:
    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}

    def counter(self, name: str, help_text: str = "", label_names: list[str] | None = None) -> Counter:
        if name not in self._counters:
            self._counters[name] = Counter(name, help_text, label_names or [])
        return self._counters[name]

    def gauge(self, name: str, help_text: str = "", label_names: list[str] | None = None) -> Gauge:
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, help_text, label_names or [])
        return self._gauges[name]

    def histogram(self, name: str, help_text: str = "", label_names: list[str] | None = None) -> Histogram:
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, help_text, label_names or [])
        return self._histograms[name]

    def collect(self) -> list[MetricSample]:
        samples = []
        now = datetime.now(timezone.utc)
        for c in self._counters.values():
            for key, val in c._values.items():
                labels = dict(zip(c._labels, key))
                samples.append(MetricSample(name=c._name, labels=labels, value=val, timestamp=now))
        for g in self._gauges.values():
            for key, val in g._values.items():
                labels = dict(zip(g._labels, key))
                samples.append(MetricSample(name=g._name, labels=labels, value=val, timestamp=now))
        return samples

    def render_prometheus(self) -> str:
        lines = []
        for c in self._counters.values():
            if c._help:
                lines.append(f"# HELP {c._name} {c._help}")
            lines.append(f"# TYPE {c._name} counter")
            for key, val in c._values.items():
                lbl = ",".join(f'{k}="{v}"' for k, v in zip(c._labels, key) if v)
                lines.append(f"{c._name}{{{lbl}}} {val}")
        for g in self._gauges.values():
            if g._help:
                lines.append(f"# HELP {g._name} {g._help}")
            lines.append(f"# TYPE {g._name} gauge")
            for key, val in g._values.items():
                lbl = ",".join(f'{k}="{v}"' for k, v in zip(g._labels, key) if v)
                lines.append(f"{g._name}{{{lbl}}} {val}")
        for h in self._histograms.values():
            if h._help:
                lines.append(f"# HELP {h._name} {h._help}")
            lines.append(f"# TYPE {h._name} histogram")
            for key, lst in h._values.items():
                lbl = ",".join(f'{k}="{v}"' for k, v in zip(h._labels, key) if v)
                n = len(lst)
                s = sum(lst)
                lines.append(f"{h._name}_count{{{lbl}}} {n}")
                lines.append(f"{h._name}_sum{{{lbl}}} {s}")
        return "\n".join(lines) + "\n"

    def reset_all(self) -> None:
        for c in self._counters.values():
            c._values.clear()
        for g in self._gauges.values():
            g._values.clear()
        for h in self._histograms.values():
            h._values.clear()


def get_metrics() -> Metrics:
    global _metrics
    if _metrics is None:
        _metrics = Metrics()
        _metrics.counter("agentforge_agent_runs_total", "Total agent runs", ["agent_name"])
        _metrics.histogram("agentforge_agent_run_duration_seconds", "Agent run duration", ["agent_name"])
        _metrics.counter("agentforge_tool_calls_total", "Tool calls", ["tool_name", "success"])
        _metrics.counter("agentforge_llm_requests_total", "LLM requests", ["provider", "model"])
        _metrics.counter("agentforge_llm_tokens_total", "LLM tokens", ["provider", "model", "type"])
        _metrics.counter("agentforge_pipeline_runs_total", "Pipeline runs", ["pipeline_name"])
        _metrics.gauge("agentforge_active_agents", "Currently active agents")
    return _metrics
