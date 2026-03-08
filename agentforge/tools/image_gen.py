"""Image generation tool — generate images from text prompts via DALL-E or Stability AI."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import httpx

from agentforge.tools.base import Tool, ToolResult


class ImageGenTool(Tool):
    """Generate images from text prompts using DALL-E 3 or Stability AI."""

    def __init__(
        self,
        provider: str = "dalle",
        api_key: str | None = None,
        save_dir: str | Path | None = None,
    ) -> None:
        self._provider = provider.lower()
        self._api_key = api_key
        self._save_dir = Path(save_dir).resolve() if save_dir else None
        if self._save_dir and not self._save_dir.is_dir():
            self._save_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "image_gen"

    @property
    def description(self) -> str:
        return "Generate images from text prompts using DALL-E 3 or Stability AI. Returns URLs or local paths."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Image description (required)."},
                "style": {
                    "type": "string",
                    "enum": ["vivid", "natural", "photorealistic", "anime", "digital-art"],
                    "description": "Style: vivid/natural for DALL-E; photorealistic/anime/digital-art for Stability.",
                },
                "size": {"type": "string", "enum": ["1024x1024", "1792x1024", "1024x1792"], "default": "1024x1024"},
                "quality": {"type": "string", "enum": ["standard", "hd"], "default": "standard"},
                "n": {"type": "integer", "description": "Number of images (1-4).", "default": 1},
            },
            "required": ["prompt"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        prompt = (kwargs.get("prompt") or "").strip()
        if not prompt:
            return ToolResult(success=False, output="", error="'prompt' is required")
        n = min(max(int(kwargs.get("n", 1)), 1), 4)
        try:
            if self._provider == "dalle":
                return await self._generate_dalle(
                    prompt,
                    kwargs.get("style", "vivid"),
                    kwargs.get("size", "1024x1024"),
                    kwargs.get("quality", "standard"),
                    n,
                )
            if self._provider == "stability":
                return await self._generate_stability(prompt, kwargs.get("style", "digital-art"), n)
            return ToolResult(success=False, output="", error=f"Unknown provider: {self._provider}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _generate_dalle(
        self,
        prompt: str,
        style: str,
        size: str,
        quality: str,
        n: int,
    ) -> ToolResult:
        key = self._api_key or __import__("os").environ.get("OPENAI_API_KEY")
        if not key:
            return ToolResult(success=False, output="", error="OPENAI_API_KEY or api_key required for DALL-E")
        payload = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": n,
            "size": size,
            "quality": quality,
            "response_format": "url",
            "style": "vivid" if style == "vivid" else "natural",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        urls = [img["url"] for img in data.get("data", [])]
        if self._save_dir and urls:
            paths = []
            for url in urls:
                r2 = await httpx.AsyncClient().get(url)
                r2.raise_for_status()
                path = self._save_dir / f"{uuid.uuid4().hex[:12]}.png"
                path.write_bytes(r2.content)
                paths.append(str(path))
            return ToolResult(success=True, output="\n".join(paths), metadata={"urls": urls, "paths": paths})
        return ToolResult(success=True, output="\n".join(urls), metadata={"urls": urls})

    async def _generate_stability(self, prompt: str, style: str, n: int) -> ToolResult:
        key = self._api_key or __import__("os").environ.get("STABILITY_API_KEY")
        if not key:
            return ToolResult(success=False, output="", error="STABILITY_API_KEY or api_key required for Stability")
        payload = {
            "text_prompts": [{"text": prompt}],
            "cfg_scale": 7,
            "height": 1024,
            "width": 1024,
            "samples": n,
            "style_preset": style if style in ("photorealistic", "anime", "digital-art") else "digital-art",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        urls = []
        for i, art in enumerate(data.get("artifacts", [])):
            b64 = art.get("base64")
            if not b64:
                continue
            import base64
            raw = base64.b64decode(b64)
            if self._save_dir:
                path = self._save_dir / f"{uuid.uuid4().hex[:12]}.png"
                path.write_bytes(raw)
                urls.append(str(path))
            else:
                urls.append(f"[Image {i+1} base64 length {len(raw)}]")
        return ToolResult(success=True, output="\n".join(urls), metadata={"count": len(urls)})
