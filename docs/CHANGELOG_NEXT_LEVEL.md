# Changelog — Next-Level Release

This document summarizes the next-level additions to AgentForge (post-0.3.0).

---

## New Tools

- **SummarizeTool** (`agentforge.tools.summarize`): Summarize long text with strategies head, tail, head_tail, sentences.
- **FetchURLTool** (`agentforge.tools.fetch_url`): Fetch URL content with optional HTML stripping and truncation.
- **JSONPathTool** (`agentforge.tools.json_path`): Query JSON with simple path expressions ($.key.nested, $.arr[0], $.items[*]).
- **RegexTool** (`agentforge.tools.regex_tool`): Find or replace using regex (find returns matches; replace substitutes).
- **EnvTool** (`agentforge.tools.env_tool`): Read env var by name or list safe keys (sensitive keys masked).
- **HashTool** (`agentforge.tools.hash_tool`): Hash (MD5/SHA1/SHA256) or Base64 encode/decode text.
- **YamlTool** (`agentforge.tools.yaml_tool`): Parse YAML/JSON to JSON or dump JSON to YAML.

All of the above are registered in `agentforge.tools` and in the main package `__init__.py` so they appear in `agentforge tools` CLI and `/api/v1/tools`.

---

## Core

- **agentforge.core.config**: Extended `AgentConfig` (adds provider, tools list) for API/CLI; `PipelineConfig`, `ServerConfig`.
- **agentforge.core.pipeline_events**: `PipelineEventBus`, `PipelineEvent`, `PipelineEventType`; subscribe/emit; middleware (step_name, context) -> context; helpers `logging_middleware`, `truncate_context_middleware`; `get_pipeline_event_bus()`, `reset_pipeline_event_bus()`.
- **agentforge.core.validation**: `validate_pipeline_dict(data)` and `validate_pipeline_yaml_string(yaml_str)` return list of error strings; `ValidationError` (optional use).
- **agentforge.core.middleware**: `metrics_middleware`, `redact_context_middleware`, `timing_middleware`, `create_truncate_middleware(N)`, `register_default_middleware()`.

---

## Observability

- **agentforge.observability.events**: `StructuredEvent`, `EventKind` (agent_start, agent_end, tool_call, tool_result, pipeline_step, error, metric); `emit_event()`, `register_event_handler()`, `clear_event_handlers()`.
- Exported from `agentforge.observability` alongside tracer and metrics.

---

## Server

- **agentforge.server.routes_advanced**: New router with GET `/api/v1/readyz`, GET `/api/v1/metrics`, GET `/api/v1/config`, GET `/api/v1/runs`. Mounted in `agentforge.server.app`.

---

## CLI

- **agentforge validate &lt;file.yaml&gt;** — Validates pipeline YAML (name, steps, no duplicate names).
- **agentforge config** — Prints safe config (version, timeouts, port).
- **agentforge workflows [--dir PATH]** — Lists workflow YAML files.

---

## Schemas

- **agentforge.schemas.api**: Pydantic models for API: `RunRequestSchema`, `RunResponseSchema`, `EventItemSchema`, `PipelineRequestSchema`, `PipelineResponseSchema`, `StepResultSchema`, `HealthSchema`, `ErrorSchema`, `ErrorDetailSchema`. Central place for request/response validation and OpenAPI.

---

## Utils

- **agentforge.utils.retry**: `@retry_async(...)` and `@retry_sync(...)` with exponential backoff and jitter.
- **agentforge.utils.sanitize**: `truncate()`, `redact_secrets()`, `sanitize_for_log()` for safe logging.

---

## Workflows

- **workflows/summarize_doc.yaml**: fetch -> summarize -> review.
- **workflows/qa_chain.yaml**: research -> answer -> fact_check.

---

## Documentation

- **docs/ARCHITECTURE.md**: High-level architecture (agents, pipeline, orchestrator, tools, config, events, server, CLI, extension points, security).
- **docs/NEXT_LEVEL.md**: Next-level guide (new tools, config, validation, events, middleware, observability, server endpoints, CLI, utils, workflows, best practices).
- **docs/API_REFERENCE.md**: REST and WebSocket API reference (endpoints, request/response, query params).
- **docs/RUNBOOK.md**: Operational runbook (prereqs, server, CLI, API, events, middleware, observability, validation, security, retries, tools reference, troubleshooting, scaling).
- **docs/CHANGELOG_NEXT_LEVEL.md**: This file.

---

## Tests and Examples

- **tests/integration/test_next_level_tools.py**: Tests for summarize, json_path, regex, env tools.
- **tests/integration/test_pipeline_events.py**: Tests for event bus, middleware, helpers.
- **tests/integration/test_server_advanced.py**: Tests for readyz, metrics, config, runs endpoints.
- **tests/integration/test_validation.py**: Tests for validate_pipeline_dict and validate_pipeline_yaml_string.
- **examples/next_level_demo.py**: Demo of summarize, json_path, regex, validation, event bus.

---

## Breaking Changes

- None. All additions are additive. The server and CLI may still reference `agentforge.core.config.AgentConfig`; that module now exists and extends the core `AgentConfig` with provider and tools. If your code previously constructed `Agent(config=config)` without llm/tools, you must now resolve LLM and tools from config and use `Agent(config=config.to_agent_config(), llm=..., tools=...)` or equivalent.

---

## Migration

- To use new tools: they are auto-registered; use `agentforge tools` or include them in your agent’s tool list by name.
- To use pipeline events: `from agentforge.core.pipeline_events import get_pipeline_event_bus` and subscribe/add_middleware.
- To use validation: `from agentforge.core.validation import validate_pipeline_dict` and run in CI.
- To use observability events: `from agentforge.observability.events import register_event_handler, emit_event`.

---

*Next-level release — 2025.*
