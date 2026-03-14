# AgentForge Runbook (Next-Level)

Operational runbook for running, debugging, and scaling AgentForge.

---

## 1. Prerequisites

- Python 3.11+
- Environment variables (see README): at least one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`; optional `OLLAMA_BASE_URL`, `CHROMA_PERSIST_DIR`, `AGENTFORGE_HOST`, `AGENTFORGE_PORT`.
- Optional: PyYAML for pipeline YAML loading; httpx for fetch_url and web_search tools.

---

## 2. Starting the Server

```bash
# From repo root
python -m agentforge.cli serve --host 0.0.0.0 --port 8000

# Or with uvicorn directly
uvicorn agentforge.server.app:app --host 0.0.0.0 --port 8000
```

- Health: `GET /api/v1/health`
- Readiness: `GET /api/v1/readyz` (use in Kubernetes readiness probe)
- Docs: `GET /docs` or `GET /redoc`

---

## 3. Running a Single Task (CLI)

```bash
agentforge run "What is the capital of France?" --agent default
agentforge run "Summarize this: ..." --model gpt-4o --provider openai
```

- If the CLI reports "AgentConfig" or "Agent" errors, ensure you have an LLM provider configured and that the code path uses the correct Agent constructor (config + llm + tools).

---

## 4. Running a Pipeline (CLI)

```bash
agentforge pipeline /path/to/workflows/summarize_doc.yaml
agentforge validate /path/to/workflows/summarize_doc.yaml  # validate first
```

- Validate all pipeline YAMLs before deploy: `agentforge validate <file.yaml>`.

---

## 5. Listing Tools and Workflows

```bash
agentforge tools          # list registered tools
agentforge workflows      # list workflow YAMLs in default dir
agentforge workflows --dir /custom/path
agentforge config         # show safe config
agentforge version        # show version
```

---

## 6. API Usage

- **POST /api/v1/run**: Body `{ "task": "...", "agent_name": "default", "tools": [] }`. Returns events and final_answer.
- **POST /api/v1/pipeline**: Body `{ "yaml_content": "name: ...\nsteps: ..." }`. Returns steps and success.
- **GET /api/v1/readyz**: Readiness; use in K8s.
- **GET /api/v1/metrics**: Counters/gauges summary.
- **GET /api/v1/config**: Safe config (no secrets).
- **GET /api/v1/runs**: List runs (stub unless wired to RunStore).

---

## 7. Pipeline Events and Middleware

- Subscribe to pipeline events: `get_pipeline_event_bus().subscribe(handler)`.
- Add middleware: `get_pipeline_event_bus().add_middleware(async (step_name, context) -> context)`.
- Pre-built middleware: `logging_middleware`, `truncate_context_middleware`, `metrics_middleware`, `redact_context_middleware`, `create_truncate_middleware(N)`.
- Register defaults: `register_default_middleware()` (logging + truncate).

---

## 8. Observability

- **Structured events**: `register_event_handler(handler)`; emit with `emit_event(StructuredEvent(...))`. Kinds: agent_start, agent_end, tool_call, tool_result, pipeline_step, error, metric.
- **Tracer**: Use `get_tracer()` and spans for distributed tracing.
- **Metrics**: Use `get_metrics()` for counters/gauges/histograms. Expose via `/api/v1/metrics` or your own Prometheus endpoint.

---

## 9. Validation

- Pipeline YAML: `validate_pipeline_dict(data)` or `validate_pipeline_yaml_string(yaml_str)` returns a list of error strings; empty list means valid.
- Use in CI: `agentforge validate workflows/*.yaml` (loop in a script).

---

## 10. Security

- Do not log raw API keys or secrets. Use `sanitize_for_log(obj)` and `redact_secrets(text)` from `agentforge.utils.sanitize`.
- Env tool: only non-sensitive env keys are listable; keys with prefixes like SECRET, KEY, PASSWORD are blocked for get.
- Config export endpoint returns no secrets.

---

## 11. Retries and Backoff

- Use `@retry_async(max_attempts=3, delay=1, backoff=2, jitter=0.1)` or `@retry_sync(...)` from `agentforge.utils.retry` for transient failures.

---

## 12. Next-Level Tools Reference

- **summarize**: text, strategy (head/tail/head_tail/sentences), max_chars, max_sentences.
- **fetch_url**: url, strip_html, max_chars, timeout_seconds.
- **json_path**: json_text, path (e.g. $.a.b[0]).
- **regex**: text, pattern, mode (find/replace), replacement, max_matches, ignore_case.
- **env**: action (get/list), key (for get).
- **hash**: action (hash/base64_encode/base64_decode), text, algorithm (md5/sha1/sha256).
- **yaml_json**: text, format (yaml_to_json/json_to_yaml/parse).

---

## 13. Troubleshooting

- **"No module named 'agentforge.core.config'"**: Ensure you have the next-level `agentforge/core/config.py` (re-exports/extends AgentConfig for API/CLI).
- **Pipeline step fails**: Check step name, agent name, and dependency names in YAML; run `agentforge validate <file>`.
- **Tool not found**: Ensure the tool is registered via `register_tool(ToolClass)` or entry point `agentforge.tools`; run `agentforge tools` to list.
- **WebSocket stream fails**: Check that the server uses the same Agent constructor as in your run (config + llm + tools); adapt server code if it currently only passes config.

---

## 14. Scaling and Limits

- Pipeline concurrency is per-layer (all steps in a layer can run in parallel). Limit concurrency via orchestrator or external queue if needed.
- Truncate long context with `truncate_context_middleware` or `create_truncate_middleware(5000)` to avoid memory and token limits.
- Use `max_chars` in fetch_url and summarize to cap output size.

---

*Last updated: next-level release.*
