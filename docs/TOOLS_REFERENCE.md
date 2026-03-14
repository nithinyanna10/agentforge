# AgentForge Tools Reference (Next-Level)

Complete reference for all built-in tools, including next-level additions.

---

## Base

Every tool implements: `name`, `description`, `parameters` (JSON Schema), `execute(**kwargs) -> ToolResult`. ToolResult has: `success`, `output`, `error`, `metadata`.

---

## WebSearchTool

- **name**: `web_search`
- **description**: Search the web using DuckDuckGo; returns titles, URLs, snippets.
- **parameters**: `query` (string, required), `num_results` (integer, default 5).
- **returns**: Formatted search results text.

---

## CodeExecutorTool

- **name**: `code_executor`
- **description**: Execute Python code in a sandbox.
- **parameters**: (see tool definition) code string, timeout, etc.
- **returns**: Stdout/stderr and result.

---

## FileOpsTool

- **name**: `file_ops`
- **description**: Read, write, list files within a base directory.
- **parameters**: action, path, content (for write).
- **returns**: File contents or listing.

---

## APICallerTool

- **name**: `api_caller`
- **description**: Make HTTP GET/POST/etc. requests.
- **parameters**: url, method, headers, body.
- **returns**: Response body and status.

---

## SqlQueryTool

- **name**: `sql_query`
- **description**: Run SQL queries (with configured DB).
- **parameters**: query, params.
- **returns**: Rows or error.

---

## ShellCommandTool

- **name**: `shell_command`
- **description**: Run shell commands.
- **parameters**: command, cwd, timeout.
- **returns**: Stdout, stderr, exit code.

---

## DateTimeTool

- **name**: `datetime_tool`
- **description**: Current date/time, format, parse.
- **parameters**: action, format, timezone.
- **returns**: Formatted date/time string.

---

## MathExpressionTool

- **name**: `math_expression`
- **description**: Evaluate a math expression safely.
- **parameters**: expression (string).
- **returns**: Result number as string.

---

## GitHubTool

- **name**: `github`
- **description**: Interact with GitHub API (issues, PRs, etc.).
- **parameters**: action, repo, path, etc.
- **returns**: API response or error.

---

## DocumentReaderTool

- **name**: `document_reader`
- **description**: Read and extract text from documents (PDF, etc.).
- **parameters**: path or content, format.
- **returns**: Extracted text.

---

## ImageGenTool

- **name**: `image_gen`
- **description**: Generate images from prompts (e.g. DALL-E).
- **parameters**: prompt, size, n.
- **returns**: URL or base64 image.

---

## SummarizeTool (Next-Level)

- **name**: `summarize`
- **description**: Summarize long text with configurable strategy.
- **parameters**:
  - `text` (string, required)
  - `strategy` (string, required): `head`, `tail`, `head_tail`, `sentences`
  - `max_chars` (integer, default 500) for head/tail/head_tail
  - `max_sentences` (integer, default 5) for strategy `sentences`
- **returns**: Summarized string in `output`; `metadata.strategy`.

---

## FetchURLTool (Next-Level)

- **name**: `fetch_url`
- **description**: Fetch URL content; optional HTML strip and truncation.
- **parameters**:
  - `url` (string, required)
  - `strip_html` (boolean, default true)
  - `max_chars` (integer, default 50000)
  - `timeout_seconds` (number, default 30)
- **returns**: Body or stripped text; `metadata.url`, `metadata.content_type`, `metadata.length`.

---

## JSONPathTool (Next-Level)

- **name**: `json_path`
- **description**: Query JSON with path expressions.
- **parameters**: `json_text` (string), `path` (string, e.g. `$.a.b[0]`, `$.items[*].id`).
- **returns**: Value(s) at path as JSON string; `metadata.path`.

---

## RegexTool (Next-Level)

- **name**: `regex`
- **description**: Find or replace using regular expressions.
- **parameters**:
  - `text` (string)
  - `pattern` (string)
  - `mode` (string): `find` or `replace`
  - `replacement` (string, for replace)
  - `max_matches` (integer, default 20 for find)
  - `ignore_case` (boolean, default false)
- **returns**: Matches (one per line) or replaced text; `metadata.count` or `metadata.mode`.

---

## EnvTool (Next-Level)

- **name**: `env`
- **description**: Read env var or list safe env keys (sensitive keys masked).
- **parameters**: `action` (string): `get` or `list`; `key` (string, required for get).
- **returns**: Value or "(not set)" for get; newline-separated keys for list. Sensitive prefixes (SECRET, KEY, PASSWORD, TOKEN, etc.) are not listable and get is rejected.

---

## HashTool (Next-Level)

- **name**: `hash`
- **description**: Hash text or Base64 encode/decode.
- **parameters**:
  - `action` (string): `hash`, `base64_encode`, `base64_decode`
  - `text` (string, required)
  - `algorithm` (string, default sha256): `md5`, `sha1`, `sha256` for action hash
- **returns**: Hash hex string or encoded/decoded string; `metadata.algorithm` or `metadata.action`.

---

## YamlTool (Next-Level)

- **name**: `yaml_json`
- **description**: Parse YAML/JSON to JSON or dump JSON to YAML.
- **parameters**: `text` (string), `format` (string): `yaml_to_json`, `json_to_yaml`, `parse` (auto-detect).
- **returns**: Converted string. Requires PyYAML for YAML.

---

## Usage in agents

- Register tools with `register_tool(ToolClass)` or via entry point `agentforge.tools`.
- Pass tool instances to `Agent(..., tools=[...])` or reference by name in API/CLI tool list.
- CLI: `agentforge tools` lists all registered tools.

---

*Last updated: next-level release.*
