"""NVIDIA NIM scraper using the direct integrate.api.nvidia.com API."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from playwright.async_api import Page

from web2api.scraper import BaseScraper, ScrapeResult

API_BASE = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "meta/llama-3.1-70b-instruct"
API_KEY_ENV = "NVIDIA_API_KEY"


def _http_json(url: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        if exc.code == 401:
            raise RuntimeError(
                f"NVIDIA API authorization failed. Set {API_KEY_ENV} and try again."
            ) from None
        raise RuntimeError(f"NVIDIA API request failed ({exc.code}): {detail or exc.reason}") from None
    except URLError as exc:
        raise RuntimeError(f"NVIDIA API network error: {exc.reason}") from None


def _as_float(value: Any, *, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    return float(value)


def _as_int(value: Any, *, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    return int(value)


class Scraper(BaseScraper):
    def supports(self, endpoint: str) -> bool:
        return endpoint in {"models", "chat"}

    async def scrape(self, endpoint: str, page: Page, params: dict[str, Any]) -> ScrapeResult:
        if endpoint == "models":
            return await self._models(params)
        if endpoint == "chat":
            return await self._chat(params)
        raise RuntimeError(f"Unsupported endpoint: {endpoint}")

    async def _models(self, params: dict[str, Any]) -> ScrapeResult:
        payload = await asyncio.to_thread(_http_json, f"{API_BASE}/models")
        owner = (params.get("owner") or "").strip().lower()
        prefix = (params.get("prefix") or "").strip().lower()

        items: list[dict[str, Any]] = []
        for model in payload.get("data", []):
            model_id = str(model.get("id", ""))
            model_owner = str(model.get("owned_by", ""))
            if owner and model_owner.lower() != owner:
                continue
            if prefix and not model_id.lower().startswith(prefix):
                continue
            items.append({
                "id": model_id,
                "owner": model_owner,
                "object": model.get("object"),
                "created": model.get("created"),
            })

        return ScrapeResult(items=items)

    async def _chat(self, params: dict[str, Any]) -> ScrapeResult:
        prompt = (params.get("query") or "").strip()
        if not prompt:
            raise RuntimeError("Missing prompt — pass q=<prompt>")

        model = (params.get("model") or DEFAULT_MODEL).strip()
        system = (params.get("system") or "").strip()
        temperature = _as_float(params.get("temperature"), default=None)
        top_p = _as_float(params.get("top_p"), default=None)
        max_tokens = _as_int(params.get("max_tokens"), default=None)

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if top_p is not None:
            body["top_p"] = top_p
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        payload = await asyncio.to_thread(
            _http_json,
            f"{API_BASE}/chat/completions",
            method="POST",
            body=body,
        )

        choices = payload.get("choices") or []
        first = choices[0] if choices else {}
        message = first.get("message") or {}
        usage = payload.get("usage") or {}

        item = {
            "prompt": prompt,
            "response": message.get("content", ""),
            "model": payload.get("model", model),
            "finish_reason": first.get("finish_reason"),
        }
        if usage:
            item["usage"] = json.dumps(usage)
        if system:
            item["system"] = system

        return ScrapeResult(items=[item])
