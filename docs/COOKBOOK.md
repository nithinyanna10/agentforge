# AgentForge Cookbook (Next-Level)

Copy-paste recipes for common tasks using next-level features.

---

## 1. Validate a pipeline in Python

```python
from agentforge.core.validation import validate_pipeline_dict, validate_pipeline_yaml_string

# From dict
data = {"name": "my_pipeline", "steps": [{"name": "s1", "agent": "researcher"}]}
errors = validate_pipeline_dict(data)
if errors:
    for e in errors:
        print(e)
else:
    print("Valid")

# From YAML string
yaml_str = "name: p\nsteps:\n  - name: s1\n    agent: writer\n"
errors = validate_pipeline_yaml_string(yaml_str)
```

---

## 2. Subscribe to pipeline events

```python
from agentforge.core.pipeline_events import get_pipeline_event_bus, PipelineEventType

bus = get_pipeline_event_bus()

def on_event(event):
    print(event.type.value, event.step_name, event.payload)

bus.subscribe(on_event)
# When pipeline runs, on_event will be called for each event
```

---

## 3. Add truncation middleware

```python
from agentforge.core.pipeline_events import get_pipeline_event_bus
from agentforge.core.pipeline_events import truncate_context_middleware

bus = get_pipeline_event_bus()
bus.add_middleware(lambda sn, ctx: truncate_context_middleware(sn, ctx, max_value_chars=3000))
```

---

## 4. Emit structured events

```python
from agentforge.observability.events import emit_event, EventKind, StructuredEvent

emit_event(StructuredEvent(
    kind=EventKind.TOOL_CALL,
    name="web_search",
    message="Searching for ...",
    metadata={"query": "..."},
))
```

---

## 5. Register an event handler (e.g. for logging)

```python
from agentforge.observability.events import register_event_handler, StructuredEvent
import json

def log_to_stdout(event: StructuredEvent):
    print(json.dumps(event.to_dict()))

register_event_handler(log_to_stdout)
```

---

## 6. Use SummarizeTool in code

```python
from agentforge.tools.summarize import SummarizeTool

tool = SummarizeTool()
result = await tool.execute(text="Long text ...", strategy="sentences", max_sentences=5)
print(result.output)
```

---

## 7. Use JSONPathTool

```python
from agentforge.tools.json_path import JSONPathTool

tool = JSONPathTool()
result = await tool.execute(
    json_text='{"data": {"items": [{"name": "A"}, {"name": "B"}]}}',
    path="$.data.items[*].name"
)
print(result.output)  # JSON array of names
```

---

## 8. Use RegexTool for replace

```python
from agentforge.tools.regex_tool import RegexTool

tool = RegexTool()
result = await tool.execute(
    text="Hello WORLD",
    pattern="WORLD",
    mode="replace",
    replacement="Earth"
)
print(result.output)  # "Hello Earth"
```

---

## 9. Use EnvTool (list safe keys)

```python
from agentforge.tools.env_tool import EnvTool

tool = EnvTool()
result = await tool.execute(action="list")
print(result.output)  # newline-separated safe env keys
```

---

## 10. Use HashTool

```python
from agentforge.tools.hash_tool import HashTool

tool = HashTool()
result = await tool.execute(text="hello", action="hash", algorithm="sha256")
print(result.output)
```

---

## 11. Retry an async function

```python
from agentforge.utils.retry import retry_async

@retry_async(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(ConnectionError,))
async def fetch():
    ...

await fetch()
```

---

## 12. Sanitize for logging

```python
from agentforge.utils.sanitize import sanitize_for_log, redact_secrets

safe = sanitize_for_log({"key": "secret_key_abc123", "msg": "Hello"})
# safe["key"] will be redacted

text = redact_secrets("api_key=sk-xyz123")
# "api_key=***"
```

---

## 13. Use pipeline config

```python
from agentforge.core.config import PipelineConfig

config = PipelineConfig(
    default_timeout_seconds=600,
    max_concurrent_layers=4,
    default_retries=2,
    fail_fast=False,
)
```

---

## 14. Use API schemas for validation

```python
from agentforge.schemas.api import RunRequestSchema, PipelineRequestSchema

body = RunRequestSchema(task="Hello", agent_name="default", tools=[])
body = PipelineRequestSchema(yaml_content="name: p\nsteps: []")
```

---

## 15. Run default middleware

```python
from agentforge.core.middleware import register_default_middleware

bus = register_default_middleware()  # adds logging + truncate(5000)
```

---

## 16. Call readyz from Python

```python
import httpx

r = httpx.get("http://localhost:8000/api/v1/readyz")
assert r.status_code == 200
assert r.json()["ready"] is True
```

---

## 17. Call metrics endpoint

```python
import httpx

r = httpx.get("http://localhost:8000/api/v1/metrics")
data = r.json()
print(data["counters"], data["gauges"])
```

---

## 18. Validate from CLI

```bash
agentforge validate workflows/summarize_doc.yaml
agentforge validate workflows/qa_chain.yaml
```

---

## 19. List workflows

```bash
agentforge workflows
agentforge workflows --dir /path/to/yamls
```

---

## 20. Full pipeline run with event bus (pseudo-code)

```python
from agentforge.core.pipeline_events import get_pipeline_event_bus
from agentforge.core.orchestrator import Orchestrator
from agentforge.core.pipeline import Pipeline

bus = get_pipeline_event_bus()
bus.subscribe(lambda e: print(e.type.value, e.step_name))

# ... build orchestrator and pipeline ...
# When you run orchestrator.run_pipeline(pipeline, ...), emit events at each step
# in your orchestrator code (or use a wrapper that calls bus.emit).
```

---

*Use these recipes as building blocks for your own pipelines and integrations.*
