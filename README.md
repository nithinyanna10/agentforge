<div align="center">

# AgentForge

### Build, orchestrate, and deploy AI agents with production-ready pipelines

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/nithinyanna/agentforge/ci.yml?label=CI&logo=githubactions&logoColor=white)](https://github.com/nithinyanna/agentforge/actions)
[![PyPI](https://img.shields.io/pypi/v/agentforge?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/agentforge/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

<br/>

**AgentForge** is a Python framework for building autonomous AI agents that reason, use tools, and collaborate through DAG-based pipelines — from prototype to production in minutes.

[Quick Start](#-quick-start) · [Architecture](#-architecture) · [Pipelines](#-pipelines) · [API Reference](#-api-reference) · [Contributing](#-contributing)

</div>

---

## Highlights

- **Multi-agent orchestration** — Define complex workflows as directed acyclic graphs (DAGs) with conditional branching, fan-out/fan-in, and retry policies
- **ReAct loop** — Agents autonomously reason, select tools, observe results, and iterate until the task is solved
- **Multiple LLM providers** — First-class support for OpenAI, Anthropic, and Ollama/local models with a unified interface
- **Built-in tool library** — Web search, sandboxed code execution, file operations, HTTP/API calls, and more
- **Persistent memory** — Conversation history plus vector storage (ChromaDB) for long-term retrieval-augmented context
- **Real-time streaming** — Token-level streaming over WebSocket and a polished CLI experience
- **Beautiful terminal UI** — Powered by [Rich](https://github.com/Textualize/rich) with live markdown rendering, spinners, and syntax-highlighted output
- **Production API** — FastAPI server with REST + WebSocket endpoints, auth middleware, and structured logging
- **YAML-based pipelines** — Declare multi-step agent workflows in simple YAML — no Python required
- **Fully extensible** — Add custom tools, LLM providers, and memory backends with a clean plugin interface

---

## Quick Start

### Installation

```bash
pip install agentforge
```

Or install from source with dev dependencies:

```bash
git clone https://github.com/nithinyanna/agentforge.git
cd agentforge
pip install -e ".[dev]"
```

### Environment Setup

Create a `.env` file in your project root:

```dotenv
# LLM Providers (set at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional: local model via Ollama
OLLAMA_BASE_URL=http://localhost:11434

# Memory (optional, enables vector search)
CHROMA_PERSIST_DIR=./data/chroma

# Server
AGENTFORGE_HOST=0.0.0.0
AGENTFORGE_PORT=8000
```

### Hello, Agent

```python
from agentforge import Agent, Tool
from agentforge.providers import OpenAIProvider

provider = OpenAIProvider(model="gpt-4o")

agent = Agent(
    name="researcher",
    provider=provider,
    tools=[Tool.web_search(), Tool.code_exec()],
    system_prompt="You are a senior research analyst.",
)

response = agent.run("What are the latest advances in quantum error correction?")
print(response)
```

### CLI

```bash
# Interactive chat
agentforge chat --model gpt-4o

# Run a pipeline
agentforge run pipeline.yaml --input "Summarize today's AI news"

# Start the API server
agentforge serve --port 8000
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   CLI/API    │────▶│ Orchestrator │────▶│   Agents    │
└─────────────┘     └──────────────┘     └──────┬──────┘
                           │                     │
                     ┌─────▼─────┐         ┌─────▼─────┐
                     │ Pipeline  │         │  LLM API  │
                     │   (DAG)   │         │ Providers │
                     └───────────┘         └───────────┘
                                                 │
                           ┌──────────────┬──────┴──────┐
                           │    Tools     │   Memory    │
                           └──────────────┴─────────────┘
```

| Layer | Responsibility |
|---|---|
| **CLI / API** | User-facing interfaces — Rich terminal UI and FastAPI server |
| **Orchestrator** | Routes tasks, manages agent lifecycles, enforces pipeline DAGs |
| **Agents** | ReAct loop — reason → act → observe → repeat |
| **Pipeline (DAG)** | Declarative YAML workflows with steps, conditions, and data flow |
| **LLM Providers** | Unified interface to OpenAI, Anthropic, Ollama, and custom backends |
| **Tools** | Sandboxed capabilities agents can invoke (search, code, files, APIs) |
| **Memory** | Short-term conversation buffer + long-term ChromaDB vector store |

---

## Pipelines

Define multi-agent workflows in YAML:

```yaml
# pipeline.yaml
name: research-and-report
description: Research a topic, then generate a polished report

steps:
  - id: research
    agent: researcher
    prompt: "Find the top 5 recent papers on {{ topic }}"
    tools: [web_search]

  - id: summarize
    agent: writer
    prompt: "Summarize these findings into an executive report:\n{{ research.output }}"
    depends_on: [research]

  - id: review
    agent: reviewer
    prompt: "Review this report for accuracy and clarity:\n{{ summarize.output }}"
    depends_on: [summarize]
    retry: 2
```

Run it from Python:

```python
from agentforge.pipeline import Pipeline

pipeline = Pipeline.from_yaml("pipeline.yaml")
result = pipeline.execute(variables={"topic": "quantum computing"})

print(result["review"].output)
```

Or from the CLI:

```bash
agentforge run pipeline.yaml --var topic="quantum computing"
```

---

## Available Tools

| Tool | Description | Key |
|---|---|---|
| **Web Search** | Search the web via Google/Bing/SerpAPI | `web_search` |
| **Code Execution** | Run Python in a sandboxed subprocess | `code_exec` |
| **File Operations** | Read, write, list, and delete files | `file_ops` |
| **HTTP / API Calls** | Make arbitrary HTTP requests | `http_request` |
| **Shell** | Execute shell commands (restricted mode available) | `shell` |
| **Database Query** | Run SQL against SQLite/PostgreSQL | `db_query` |
| **Vector Search** | Semantic search over ChromaDB collections | `vector_search` |
| **Calculator** | Evaluate mathematical expressions | `calculator` |

### Custom Tools

```python
from agentforge.tools import tool

@tool(name="weather", description="Get current weather for a city")
def get_weather(city: str) -> str:
    import httpx
    resp = httpx.get(f"https://wttr.in/{city}?format=3")
    return resp.text
```

---

## Configuration

All settings can be provided via environment variables or a `agentforge.toml` file.

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `AGENTFORGE_HOST` | `0.0.0.0` | API server bind host |
| `AGENTFORGE_PORT` | `8000` | API server bind port |
| `AGENTFORGE_LOG_LEVEL` | `INFO` | Logging level |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB storage directory |
| `AGENTFORGE_MAX_STEPS` | `25` | Max ReAct loop iterations per agent |
| `AGENTFORGE_TIMEOUT` | `300` | Agent execution timeout (seconds) |

---

## API Reference

Start the server:

```bash
agentforge serve
```

### `POST /v1/agent/run`

Run an agent synchronously.

```bash
curl -X POST http://localhost:8000/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "researcher",
    "prompt": "Explain CRISPR in simple terms",
    "model": "gpt-4o"
  }'
```

### `POST /v1/pipeline/run`

Execute a pipeline.

```bash
curl -X POST http://localhost:8000/v1/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline": "research-and-report",
    "variables": {"topic": "gene therapy"}
  }'
```

### `WebSocket /v1/agent/stream`

Stream agent responses token-by-token.

```javascript
const ws = new WebSocket("ws://localhost:8000/v1/agent/stream");
ws.send(JSON.stringify({ agent: "researcher", prompt: "Latest on fusion energy" }));
ws.onmessage = (e) => process.stdout.write(JSON.parse(e.data).token);
```

### `GET /v1/health`

```bash
curl http://localhost:8000/v1/health
# {"status": "ok", "version": "0.1.0"}
```

---

## Development

### Setup

```bash
git clone https://github.com/nithinyanna/agentforge.git
cd agentforge
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest -v                         # all tests
pytest --cov=agentforge -v        # with coverage
pytest tests/test_agent.py -k react  # specific test
```

### Lint & Format

```bash
ruff check .            # lint
ruff format .           # format
mypy agentforge         # type check
```

### Project Structure

```
agentforge/
├── __init__.py
├── agent.py            # Core Agent & ReAct loop
├── orchestrator.py     # Multi-agent orchestration
├── pipeline.py         # DAG pipeline engine
├── providers/          # LLM provider adapters
│   ├── openai.py
│   ├── anthropic.py
│   └── ollama.py
├── tools/              # Built-in tool implementations
│   ├── web_search.py
│   ├── code_exec.py
│   └── ...
├── memory/             # Conversation + vector memory
│   ├── buffer.py
│   └── chroma.py
├── server.py           # FastAPI application
├── cli.py              # Rich terminal interface
└── config.py           # Settings & environment loading
```

---

## Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feat/my-feature`
3. **Write tests** for your changes
4. **Ensure** all checks pass: `ruff check . && pytest`
5. **Submit** a pull request


---

## License

[MIT](LICENSE) &copy; 2026 Nithin Yanna
