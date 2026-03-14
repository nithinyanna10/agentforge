# AgentForge Architecture (Next-Level)

This document describes the architecture of AgentForge for developers and operators.

## Overview

AgentForge is a multi-agent orchestration framework. It provides:

- **Agents**: Single autonomous units that reason (ReAct loop) and use tools.
- **Orchestrator**: Registers agents and runs them in single, sequential, parallel, or pipeline modes.
- **Pipeline**: A DAG of steps; each step is an agent with input mapping from prior steps.
- **Tools**: Pluggable tools (web search, code execution, file ops, API calls, etc.) used by agents.
- **Observability**: Tracing, metrics, and structured events.

## Core Components

### Agent (`agentforge.core.agent`)

- **AgentConfig**: name, role, system_prompt, model, temperature, max_tokens, max_react_steps, retry_attempts.
- **Agent**: Holds an LLM provider, a set of tools, optional memory and run_store. Runs a ReAct loop: think -> optional tool call -> observe until answer or step limit.
- **AgentResult**: answer, tool_calls (list of ToolCallRecord), thinking_steps, duration_seconds, metadata.
- **Hooks**: on_thinking, on_tool_call, on_result for streaming or logging.

### Pipeline (`agentforge.core.pipeline`)

- **PipelineStep**: name, agent_name, input_map (param -> upstream step name), depends_on, condition (optional callable), retries, timeout_seconds.
- **Pipeline**: Collection of steps; `resolve()` returns layers (topological order) for parallel execution within a layer.
- **Loading**: `Pipeline.from_yaml(path)` and `from_dict()` for YAML/dict definitions.

### Orchestrator (`agentforge.core.orchestrator`)

- Registers agents by name.
- **run_single(agent_name, task)**: One agent, one task.
- **run_sequential(agent_names, task, chain=False)**: Run agents in order; if chain=True, each agent gets the previous answer as context.
- **run_parallel(agent_names, task)**: Run all agents concurrently on the same task.
- **run_pipeline(pipeline, initial_inputs)**: Execute the DAG; for each layer, build task from input_map and context, run agents in parallel, then update context.

### Tools (`agentforge.tools`)

- **Tool**: Abstract base with name, description, parameters (JSON Schema), execute(**kwargs) -> ToolResult.
- **ToolResult**: success, output, error, metadata.
- **Built-in tools**: web_search, code_executor, file_ops, api_caller, sql_query, shell_command, datetime_tool, math_expression, github_tool, document_reader, image_gen.
- **Next-level tools**: summarize, fetch_url, json_path, regex, env.
- Tools are registered via `ext.register_tool(ToolClass)` and discovered from entry point `agentforge.tools`.

### Config (`agentforge.core.config`)

- **AgentConfig** (extended): Adds provider and tools (list of names) for API/CLI.
- **PipelineConfig**: default_timeout_seconds, max_concurrent_layers, default_retries, fail_fast.
- **ServerConfig**: host, port, CORS, api_key_header, require_api_key, timeouts.

### Pipeline Events (`agentforge.core.pipeline_events`)

- **PipelineEventType**: pipeline_start, pipeline_end, layer_start, layer_end, step_start, step_end, step_skip, step_error, context_update.
- **PipelineEvent**: type, pipeline_name, step_name, layer_index, payload, timestamp.
- **PipelineEventBus**: subscribe(handler), emit(event), add_middleware(mw). Middleware can transform context before a step runs.
- **Helpers**: logging_middleware, truncate_context_middleware.

### Observability (`agentforge.observability`)

- **Tracer**: Spans for tracing (see tracer.py).
- **Metrics**: Counter, Gauge, Histogram (see metrics.py).
- **Events**: StructuredEvent (kind, name, message, duration_seconds, metadata, timestamp, correlation_id). EventKind: agent_start, agent_end, tool_call, tool_result, pipeline_step, error, metric. register_event_handler, emit_event.

## Server (`agentforge.server`)

- **FastAPI app**: CORS, lifespan (ready flag), router at `/api/v1`.
- **Routes** (`routes.py`): POST /run, POST /pipeline, GET /agents, GET /tools, GET /health.
- **Advanced routes** (`routes_advanced.py`): GET /readyz, GET /metrics, GET /config, GET /runs.
- **WebSocket** `/ws/stream`: Stream agent execution (task, agent, tools in payload).

## CLI (`agentforge.cli`)

- **run**: Run a task with an agent (optional --agent, --model, --provider).
- **pipeline**: Run a pipeline from a YAML path.
- **serve**: Start the FastAPI server (host, port).
- **tools**: List registered tools.
- **validate**: Validate a pipeline YAML (name, steps, no duplicate names).
- **config**: Show safe config (version, timeouts, port).
- **workflows**: List workflow YAML files in a directory.
- **version**: Show version.

## Data Flow

1. **Single run**: Client -> POST /api/v1/run (task, agent_name, tools) -> Agent(config, llm, tools) -> ReAct loop -> AgentResult -> RunResponse (events, final_answer).
2. **Pipeline**: Client -> POST /api/v1/pipeline (yaml_content) -> Pipeline.from_dict -> Orchestrator.run_pipeline -> layers -> for each layer: map inputs, run agents, update context -> PipelineResponse (steps, success).
3. **Events**: PipelineEventBus.emit(step_start/step_end) and observability.emit_event(StructuredEvent) can be consumed by logging or metrics backends.

## Extension Points

- **Tools**: Implement Tool, register with register_tool(ToolClass), or use entry point `agentforge.tools`.
- **Agent factories**: register_agent_factory(name, callable) for templates.
- **Pipeline middleware**: PipelineEventBus.add_middleware(callable(step_name, context) -> context).
- **Event handlers**: register_event_handler(callable(StructuredEvent)).

## Security Considerations

- API key gate: internal API may require x-api-key (qg_*).
- Env tool: Masks variables whose names start with SECRET, KEY, PASSWORD, TOKEN, etc.
- Sanitization: sanitize_for_log() redacts secrets and truncates long strings.
- Config export: /api/v1/config returns no secrets.

## Next-Level Additions Summary

- New tools: SummarizeTool, FetchURLTool, JSONPathTool, RegexTool, EnvTool.
- core/config.py: AgentConfig (API/CLI), PipelineConfig, ServerConfig.
- core/pipeline_events.py: Event bus and middleware for pipelines.
- observability/events.py: StructuredEvent and emit_event.
- server/routes_advanced.py: readyz, metrics, config, runs.
- CLI: validate, config, workflows.
- Utils: retry_async, retry_sync, truncate, redact_secrets, sanitize_for_log.
- Workflows: summarize_doc.yaml, qa_chain.yaml.
