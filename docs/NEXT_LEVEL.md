# AgentForge Next-Level Guide

This guide describes the next-level features added to AgentForge for production and scale.

## New Tools

### SummarizeTool (`agentforge.tools.summarize`)

- **name**: `summarize`
- **Strategies**: `head` (first N chars), `tail` (last N), `head_tail` (first + last), `sentences` (first N sentences).
- **Parameters**: text, strategy, max_chars (default 500), max_sentences (default 5).
- Use case: Condense long context before sending to the LLM.

### FetchURLTool (`agentforge.tools.fetch_url`)

- **name**: `fetch_url`
- **Parameters**: url, strip_html (default True), max_chars (default 50000), timeout_seconds (default 30).
- Returns raw body or text with HTML stripped.
- Use case: Ingest web pages for research or summarization.

### JSONPathTool (`agentforge.tools.json_path`)

- **name**: `json_path`
- **Parameters**: json_text, path (e.g. `$.data.items[0].name`, `$.items[*].id`).
- Simple path evaluator; supports `[*]` for array iteration.
- Use case: Extract specific fields from API responses or config.

### RegexTool (`agentforge.tools.regex_tool`)

- **name**: `regex`
- **Parameters**: text, pattern, mode (`find` | `replace`), replacement (for replace), max_matches (default 20), ignore_case (default False).
- Use case: Search or replace in text (e.g. redaction, extraction).

### EnvTool (`agentforge.tools.env_tool`)

- **name**: `env`
- **Parameters**: action (`get` | `list`), key (for get).
- Lists only “safe” keys (sensitive prefixes like SECRET, KEY, PASSWORD are masked).
- Use case: Let the agent check non-sensitive env (e.g. LOG_LEVEL, FEATURE_FLAGS).

## Config and Validation

### AgentConfig (API/CLI)

- **agentforge.core.config.AgentConfig** extends the core AgentConfig with:
  - `provider`: openai | anthropic | ollama | auto
  - `tools`: list of tool names
- **to_agent_config()**: Returns core AgentConfig for use with Agent(config=..., llm=..., tools=...).

### PipelineConfig

- default_timeout_seconds, max_concurrent_layers, default_retries, fail_fast, metadata.

### ServerConfig

- host, port, cors_origins, api_key_header, require_api_key, request_timeout_seconds, max_request_body_size.

### CLI Validate

- `agentforge validate <path-to-pipeline.yaml>` checks:
  - Valid YAML and root is a dict
  - Presence of `steps` and non-empty
  - Each step has `name`, no duplicate names

## Pipeline Events and Middleware

### PipelineEventBus

- **get_pipeline_event_bus()**: Singleton bus.
- **subscribe(handler)**: Handler receives PipelineEvent (sync or async).
- **emit(event)**: Notify all handlers.
- **add_middleware(mw)**: Async (step_name, context) -> context; run before each step.
- **Event types**: pipeline_start, pipeline_end, layer_start, layer_end, step_start, step_end, step_skip, step_error, context_update.

### Middleware Helpers

- **logging_middleware**: Log step name and context keys.
- **truncate_context_middleware(step_name, context, max_value_chars)**: Truncate long string values in context.

## Observability

### StructuredEvent

- **EventKind**: agent_start, agent_end, tool_call, tool_result, pipeline_step, error, metric.
- **StructuredEvent**: kind, name, message, duration_seconds, metadata, timestamp, correlation_id.
- **emit_event(event)**: Send to all registered handlers.
- **register_event_handler(handler)**: Handler(StructuredEvent) -> None.

## Server Endpoints (Advanced)

- **GET /api/v1/readyz**: Readiness probe (ready, checks, version).
- **GET /api/v1/metrics**: Counters and gauges summary (and optional uptime).
- **GET /api/v1/config**: Safe config export (no secrets).
- **GET /api/v1/runs**: List recent runs (stub; wire to RunStore for real data).

## CLI Additions

- **agentforge validate &lt;file.yaml&gt;** — Validate pipeline YAML.
- **agentforge config** — Print safe config (version, timeouts, port).
- **agentforge workflows [--dir PATH]** — List workflow YAML files.

## Utilities

### Retry (`agentforge.utils.retry`)

- **retry_async(max_attempts, delay, backoff, jitter, exceptions)**: Decorator for async functions.
- **retry_sync(...)**: Same for sync functions.
- Exponential backoff with jitter to avoid thundering herd.

### Sanitize (`agentforge.utils.sanitize`)

- **truncate(text, max_length, suffix)**: Truncate with optional suffix.
- **redact_secrets(text, replacement)**: Replace API keys, passwords, tokens, sk-*, qg_*.
- **sanitize_for_log(obj, max_str)**: Recursive; redact and truncate strings for safe logging.

## Workflows

- **summarize_doc.yaml**: fetch -> summarize -> review (researcher, writer, reviewer).
- **qa_chain.yaml**: research -> answer -> fact_check.

## Best Practices

1. Use **validate** on pipeline YAMLs before committing or deploying.
2. Subscribe to **PipelineEventBus** or **register_event_handler** for metrics and alerting.
3. Use **truncate_context_middleware** when context can be large to avoid memory and token bloat.
4. Use **sanitize_for_log** when logging user input or tool outputs.
5. Use **retry_async** / **retry_sync** for transient failures (e.g. LLM or network).
