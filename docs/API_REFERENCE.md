# AgentForge API Reference (Next-Level)

Reference for REST API endpoints and request/response shapes.

## Base URL

- Local: `http://localhost:8000`
- Prefix: `/api/v1`

## Authentication

- Optional: send `x-api-key` or `X-Api-Key` with value starting with `qg_` when the server is configured to require it.

---

## POST /api/v1/run

Run a single task with one agent.

### Request body

| Field       | Type     | Required | Description                    |
|------------|----------|----------|--------------------------------|
| task       | string   | Yes      | The task to execute            |
| agent_name | string   | No       | Agent name (default: default) |
| tools      | string[] | No       | Tool names to enable           |
| model      | string   | No       | LLM model override             |
| provider   | string   | No       | LLM provider override          |

### Response (200)

| Field        | Type     | Description        |
|-------------|----------|--------------------|
| task        | string   | Echo of task       |
| agent       | string   | Agent used         |
| events      | object[] | Thinking/tool/result events |
| final_answer | string  | Agent’s final answer |

### Example

```bash
curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{"task": "What is 2+2?", "agent_name": "default"}'
```

---

## POST /api/v1/pipeline

Run a multi-step pipeline from YAML content.

### Request body

| Field       | Type   | Required | Description           |
|------------|--------|----------|-----------------------|
| yaml_content | string | Yes    | Pipeline YAML as string |

### Response (200)

| Field   | Type     | Description              |
|--------|----------|--------------------------|
| steps  | object[] | Step name, status, output |
| success | boolean | True if all steps completed |

### Example

```bash
curl -X POST http://localhost:8000/api/v1/pipeline \
  -H "Content-Type: application/json" \
  -d '{"yaml_content": "name: p\nsteps:\n  - name: s1\n    agent: researcher"}' 
```

---

## GET /api/v1/agents

List registered agent configurations.

### Response (200)

| Field   | Type     | Description      |
|--------|----------|------------------|
| agents | object[] | name, description, model, provider, tools |
| count  | integer  | Number of agents |

---

## GET /api/v1/tools

List available tools.

### Response (200)

| Field  | Type     | Description   |
|--------|----------|---------------|
| tools  | object[] | name, description, version |
| count  | integer  | Number of tools |

---

## GET /api/v1/health

Basic health check.

### Response (200)

| Field   | Type   | Description   |
|--------|--------|---------------|
| status | string | ok / degraded / error |
| version | string | AgentForge version |

---

## GET /api/v1/readyz (Next-Level)

Readiness probe (e.g. for Kubernetes).

### Response (200)

| Field   | Type    | Description        |
|--------|---------|--------------------|
| ready  | boolean | True if ready      |
| checks | object  | Per-component status |
| version | string | AgentForge version |

---

## GET /api/v1/metrics (Next-Level)

Metrics summary for monitoring.

### Response (200)

| Field           | Type   | Description        |
|----------------|--------|--------------------|
| counters       | object | Counter name -> value |
| gauges         | object | Gauge name -> value  |
| uptime_seconds | number | Server uptime       |

---

## GET /api/v1/config (Next-Level)

Safe configuration export (no secrets).

### Response (200)

| Field                            | Type   | Description        |
|----------------------------------|--------|--------------------|
| pipeline_default_timeout_seconds | number | Step timeout        |
| server_host                      | string | Bind host           |
| server_port                      | integer| Bind port           |
| version                          | string | AgentForge version  |

---

## GET /api/v1/runs (Next-Level)

List recent runs (stub; wire to RunStore for real data).

### Query parameters

| Name   | Type   | Default | Description     |
|--------|--------|--------|-----------------|
| limit  | integer| 50     | Max runs to return |
| offset | integer| 0      | Pagination offset  |

### Response (200)

| Field | Type     | Description    |
|-------|----------|----------------|
| runs  | object[] | run_id, agent, task_preview, status, created_at |
| total | integer  | Total count    |

---

## WebSocket /ws/stream

Stream agent execution in real time.

### Connect

- URL: `ws://localhost:8000/ws/stream`

### Send (JSON)

| Field  | Type     | Description     |
|--------|----------|-----------------|
| task   | string   | Task to run     |
| agent  | string   | Agent name     |
| tools  | string[] | Tool names     |

### Receive (JSON frames)

| type        | Description        |
|-------------|--------------------|
| status      | accepted           |
| thinking    | content            |
| tool_call   | tool, args         |
| tool_result | content           |
| result      | content           |
| error       | content           |
| done        | —                  |

---

## Error responses

- **400** Bad Request: invalid body or parameters.
- **422** Unprocessable Entity: validation failed (e.g. invalid YAML).
- **500** Internal Server Error: server-side failure.

Error body shape (optional):

- `detail`: string or list of `{ loc, msg, type }`
- `status_code`: integer
- `correlation_id`: string (optional)
