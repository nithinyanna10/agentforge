"""GitHub API tool — search repos, read files, list issues, and create gists."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from agentforge.tools.base import Tool, ToolResult

GITHUB_API = "https://api.github.com"


class GitHubTool(Tool):
    """Interact with GitHub: search repos, read files, list issues/PRs, create gists."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    @property
    def name(self) -> str:
        return "github"

    @property
    def description(self) -> str:
        return (
            "Search GitHub repos, get file contents, list issues/PRs, create gists, get user info, list releases. "
            "Use a GitHub PAT for higher rate limits."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "search_repos",
                        "get_file",
                        "list_issues",
                        "list_prs",
                        "create_gist",
                        "get_user",
                        "list_releases",
                    ],
                    "description": "The GitHub operation to perform.",
                },
                "query": {"type": "string", "description": "Search query for search_repos."},
                "owner": {"type": "string", "description": "Repo owner (user or org)."},
                "repo": {"type": "string", "description": "Repository name."},
                "path": {"type": "string", "description": "File path in repo for get_file."},
                "issue_state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                "filename": {"type": "string", "description": "Filename for create_gist."},
                "content": {"type": "string", "description": "Content for create_gist."},
                "description": {"type": "string", "description": "Gist description."},
                "public": {"type": "boolean", "default": False},
                "username": {"type": "string", "description": "Username for get_user."},
                "per_page": {"type": "integer", "default": 10},
            },
            "required": ["action"],
        }

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github.v3+json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "").strip().lower()
        if not action:
            return ToolResult(success=False, output="", error="'action' is required")
        dispatch = {
            "search_repos": self._search_repos,
            "get_file": self._get_file,
            "list_issues": self._list_issues,
            "list_prs": self._list_prs,
            "create_gist": self._create_gist,
            "get_user": self._get_user,
            "list_releases": self._list_releases,
        }
        handler = dispatch.get(action)
        if not handler:
            return ToolResult(success=False, output="", error=f"Unknown action: {action}")
        try:
            return await handler(**kwargs)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _search_repos(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        per_page = min(max(int(kwargs.get("per_page", 10)), 1), 30)
        if not query:
            return ToolResult(success=False, output="", error="'query' required for search_repos")
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GITHUB_API}/search/repositories",
                params={"q": query, "per_page": per_page},
                headers=self._headers(),
            )
            r.raise_for_status()
            data = r.json()
        items = data.get("items", [])
        lines = [f"Found {data.get('total_count', 0)} repos. Top {len(items)}:", ""]
        for repo in items:
            lines.append(f"- {repo.get('full_name')}: {repo.get('description') or 'No description'}")
            lines.append(f"  Stars: {repo.get('stargazers_count')}, URL: {repo.get('html_url')}")
        return ToolResult(success=True, output="\n".join(lines), metadata={"count": len(items)})

    async def _get_file(self, **kwargs: Any) -> ToolResult:
        owner = kwargs.get("owner", "").strip()
        repo = kwargs.get("repo", "").strip()
        path = kwargs.get("path", "").strip()
        if not owner or not repo or not path:
            return ToolResult(success=False, output="", error="owner, repo, and path required for get_file")
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
                headers=self._headers(),
            )
            r.raise_for_status()
            data = r.json()
        if data.get("encoding") == "base64":
            content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        else:
            content = data.get("content", "") or ""
        return ToolResult(success=True, output=content[:50000], metadata={"path": path})

    async def _list_issues(self, **kwargs: Any) -> ToolResult:
        owner = kwargs.get("owner", "").strip()
        repo = kwargs.get("repo", "").strip()
        state = kwargs.get("issue_state", "open")
        per_page = min(max(int(kwargs.get("per_page", 10)), 1), 100)
        if not owner or not repo:
            return ToolResult(success=False, output="", error="owner and repo required")
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues",
                params={"state": state, "per_page": per_page},
                headers=self._headers(),
            )
            r.raise_for_status()
            items = r.json()
        lines = [f"Issues ({state}):", ""]
        for i in items:
            if "pull_request" in i:
                continue
            lines.append(f"#{i.get('number')} {i.get('title')} - {i.get('state')}")
            lines.append(f"  {i.get('html_url')}")
        return ToolResult(success=True, output="\n".join(lines) if lines else "No issues.", metadata={"count": len([x for x in items if "pull_request" not in x])})

    async def _list_prs(self, **kwargs: Any) -> ToolResult:
        owner = kwargs.get("owner", "").strip()
        repo = kwargs.get("repo", "").strip()
        state = kwargs.get("issue_state", "open")
        per_page = min(max(int(kwargs.get("per_page", 10)), 1), 100)
        if not owner or not repo:
            return ToolResult(success=False, output="", error="owner and repo required")
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
                params={"state": state, "per_page": per_page},
                headers=self._headers(),
            )
            r.raise_for_status()
            items = r.json()
        lines = [f"Pull requests ({state}):", ""]
        for pr in items:
            lines.append(f"#{pr.get('number')} {pr.get('title')} - {pr.get('state')}")
            lines.append(f"  {pr.get('html_url')}")
        return ToolResult(success=True, output="\n".join(lines) if lines else "No PRs.", metadata={"count": len(items)})

    async def _create_gist(self, **kwargs: Any) -> ToolResult:
        filename = kwargs.get("filename", "file.txt")
        content = kwargs.get("content", "")
        description = kwargs.get("description", "")
        public = bool(kwargs.get("public", False))
        if not content:
            return ToolResult(success=False, output="", error="content required for create_gist")
        if not self._token:
            return ToolResult(success=False, output="", error="GitHub token required to create gists")
        payload = {"public": public, "files": {filename: {"content": content}}, "description": description}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{GITHUB_API}/gists", json=payload, headers=self._headers())
            r.raise_for_status()
            data = r.json()
        url = data.get("html_url", "")
        return ToolResult(success=True, output=f"Gist created: {url}", metadata={"url": url})

    async def _get_user(self, **kwargs: Any) -> ToolResult:
        username = kwargs.get("username", "").strip()
        if not username:
            return ToolResult(success=False, output="", error="username required for get_user")
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"{GITHUB_API}/users/{username}", headers=self._headers())
            r.raise_for_status()
            data = r.json()
        lines = [f"User: {data.get('login')}", f"Name: {data.get('name') or '—'}", f"Bio: {data.get('bio') or '—'}", f"Public repos: {data.get('public_repos')}", f"URL: {data.get('html_url')}"]
        return ToolResult(success=True, output="\n".join(lines))

    async def _list_releases(self, **kwargs: Any) -> ToolResult:
        owner = kwargs.get("owner", "").strip()
        repo = kwargs.get("repo", "").strip()
        per_page = min(max(int(kwargs.get("per_page", 10)), 1), 30)
        if not owner or not repo:
            return ToolResult(success=False, output="", error="owner and repo required")
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/releases",
                params={"per_page": per_page},
                headers=self._headers(),
            )
            r.raise_for_status()
            items = r.json()
        lines = ["Releases:", ""]
        for rel in items:
            lines.append(f"{rel.get('tag_name')} - {rel.get('name') or rel.get('tag_name')}")
            lines.append(f"  {rel.get('html_url')}")
        return ToolResult(success=True, output="\n".join(lines) if lines else "No releases.", metadata={"count": len(items)})
