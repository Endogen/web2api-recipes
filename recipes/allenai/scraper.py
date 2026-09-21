"""Allen AI Playground scraper — chat with OLMo, Tülu, and Molmo models.

All API calls use async HTTP (no browser needed). Supports generic
tool calling: pass `tools_url` pointing to any MCP HTTP bridge
(GET /tools, POST /tools/{name}) and the model will use those tools.

Example:
    /allenai/chat?q=Create+a+Xian+wallet&tools_url=http://localhost:8100
"""

from __future__ import annotations

import json
import logging
import mimetypes
import uuid
from typing import Any

import httpx
from playwright.async_api import Page
from web2api.network_security import validate_httpx_request
from web2api.scraper import BaseScraper, ScrapeResult

logger = logging.getLogger(__name__)

API_BASE = "https://olmo-api.allen.ai"
MAX_TOOL_ROUNDS = 5
MAX_TOOLS = 5  # Allen AI's streaming breaks with too many tool definitions

# Endpoint name → model ID mapping
_MODEL_MAP: dict[str, str] = {
    "chat": "Olmo-3.1-32B-Instruct",
    "olmo-32b": "Olmo-3.1-32B-Instruct",
    "olmo-32b-think": "Olmo-3.1-32B-Think",
    "olmo-7b": "Olmo-3-7B-Instruct",
    "tulu-8b": "cs-Llama-3.1-Tulu-3.1-8B",
    "tulu-70b": "cs-Llama-3.1-Tulu-3-70B",
    "models": None,
    "molmo2": "molmo2-8b",
    "molmo2-track": "molmo2-8b-track",
}

_SUPPORTED = set(_MODEL_MAP.keys())


# ── HTTP helpers ────────────────────────────────────────────────────

async def _http_get_json(url: str) -> Any:
    """GET JSON with redirect and private-network validation."""
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30,
        event_hooks={"request": [validate_httpx_request]},
    ) as client:
        response = await client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()


async def _http_post_json(url: str, body: dict) -> Any:
    """POST JSON with redirect and private-network validation."""
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30,
        event_hooks={"request": [validate_httpx_request]},
    ) as client:
        response = await client.post(
            url,
            json=body,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()


async def _chat_api(
    anon_id: str,
    model_id: str,
    content: str,
    parent_id: str | None = None,
    role: str | None = None,
    tool_call_id: str | None = None,
    tool_defs_json: str | None = None,
    enable_tool_calling: bool = False,
    file_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Send a message to the Allen AI chat API and parse the streamed response."""
    fields: dict[str, str | None] = {
        "content": content,
        "model": model_id,
        "host": "ai2_model_hub",
        "parent": parent_id,
        "role": role,
        "toolCallId": tool_call_id,
        "toolDefinitions": tool_defs_json,
        "enableToolCalling": "true" if enable_tool_calling else None,
    }

    upload_handles = []
    files: list[tuple[str, tuple[str, Any, str]]] = []
    try:
        for file_path in file_paths or []:
            handle = open(file_path, "rb")  # noqa: SIM115 - closed together below
            upload_handles.append(handle)
            mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            filename = file_path.rsplit("/", 1)[-1]
            files.append(("files", (filename, handle, mime)))

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=95,
            event_hooks={"request": [validate_httpx_request]},
        ) as client:
            response = await client.post(
                f"{API_BASE}/v4/threads/",
                data={name: value for name, value in fields.items() if value is not None},
                files=files or None,
                headers={"X-Anonymous-User-ID": anon_id},
            )
            response.raise_for_status()
            raw = response.text
    finally:
        for handle in upload_handles:
            handle.close()

    # Parse NDJSON stream (robust: handles newlines inside JSON values)
    response_content = ""
    thinking = None
    thread_id = None
    message_id = None
    finish_reason = None
    tool_calls: list[dict] = []
    model_used = model_id

    events: list[dict] = []
    buf = ""
    for line in raw.split("\n"):
        buf += line
        try:
            events.append(json.loads(buf))
            buf = ""
        except json.JSONDecodeError:
            buf += "\n"

    for evt in events:

        if evt.get("type") == "start":
            thread_id = evt.get("message")

        if evt.get("type") == "modelResponse" and "content" in evt:
            response_content += evt["content"]

        if evt.get("type") == "thinkingResponse" and "content" in evt:
            thinking = (thinking or "") + evt["content"]

        if "messages" in evt:
            for msg in evt["messages"]:
                if msg.get("role") == "assistant" and msg.get("final"):
                    response_content = msg.get("content") or response_content
                    thinking = msg.get("thinking") or thinking
                    finish_reason = msg.get("finishReason")
                    message_id = msg.get("id")
                    if msg.get("modelId"):
                        model_used = msg["modelId"]
                    if msg.get("toolCalls"):
                        tool_calls = msg["toolCalls"]

    return {
        "content": response_content,
        "thinking": thinking,
        "thread_id": thread_id,
        "message_id": message_id,
        "finish_reason": finish_reason,
        "model": model_used,
        "tool_calls": tool_calls,
    }


def _clean_schema(schema: dict) -> dict:
    """Strip fields from JSON Schema that Allen AI's API rejects."""
    cleaned = {}
    for key, value in schema.items():
        if key == "default":
            continue
        if key == "properties" and isinstance(value, dict):
            cleaned[key] = {
                prop_name: _clean_schema(prop_schema)
                for prop_name, prop_schema in value.items()
            }
        elif isinstance(value, dict):
            cleaned[key] = _clean_schema(value)
        else:
            cleaned[key] = value
    return cleaned


# ── Tool bridge helpers ─────────────────────────────────────────────

async def _fetch_tools(tools_url: str) -> list[dict]:
    """Fetch tool definitions from an MCP HTTP bridge."""
    return await _http_get_json(f"{tools_url}/tools")


async def _call_tool(tools_url: str, tool_name: str, args: dict) -> str:
    """Call a tool and return the result as a string."""
    try:
        result = await _http_post_json(f"{tools_url}/tools/{tool_name}", args)
        payload = result.get("result", result)
        return json.dumps(payload) if not isinstance(payload, str) else payload
    except Exception as ex:
        return json.dumps({"error": str(ex)})


# ── Scraper ─────────────────────────────────────────────────────────

class Scraper(BaseScraper):
    """Query Allen AI models with optional tool calling."""

    requires_browser = False

    def supports(self, endpoint: str) -> bool:
        return endpoint in _SUPPORTED

    async def scrape(
        self, endpoint: str, page: Page | None, params: dict[str, Any]
    ) -> ScrapeResult:
        if endpoint == "models":
            return await self._list_models()

        model_id = _MODEL_MAP[endpoint]
        query = (params.get("query") or "").strip()
        if not query:
            return ScrapeResult(
                items=[{"prompt": "", "response": "", "model": model_id}]
            )
        file_paths = params.get("file_paths") or []
        tools_url = (params.get("tools_url") or "").strip().rstrip("/")
        return await self._chat(model_id, query, tools_url, file_paths=file_paths)

    async def _chat(
        self, model_id: str, prompt: str, tools_url: str,
        file_paths: list[str] | None = None,
    ) -> ScrapeResult:
        """Send a prompt, optionally with tool calling loop."""
        anon_id = str(uuid.uuid4())

        # Discover tools from MCP HTTP bridge
        tool_defs_json = None
        if tools_url:
            tools = await _fetch_tools(tools_url)
            allen_tools = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": _clean_schema(t["parameters"]),
                }
                for t in tools[:MAX_TOOLS]
            ]
            if len(tools) > MAX_TOOLS:
                logger.warning(
                    "Limiting tools from %d to %d (Allen AI streaming limit)",
                    len(tools), MAX_TOOLS,
                )
            tool_defs_json = json.dumps(allen_tools)

        # Initial request
        result = await _chat_api(
            anon_id, model_id, prompt,
            None, None, None,
            tool_defs_json,
            bool(tools_url),
            file_paths=file_paths,
        )

        # Tool calling loop
        tool_log: list[dict[str, Any]] = []
        rounds = 0

        while (
            result.get("tool_calls")
            and tools_url
            and rounds < MAX_TOOL_ROUNDS
        ):
            rounds += 1
            parent_id = result["message_id"]

            for tool_call in result["tool_calls"]:
                tool_name = tool_call["toolName"]
                tool_call_id = tool_call["toolCallId"]
                args = tool_call.get("args", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        pass

                logger.info(
                    "Tool call round %d: %s(%s)",
                    rounds, tool_name, json.dumps(args)[:200],
                )

                # Call tool via Python HTTP
                tool_result = await _call_tool(tools_url, tool_name, args)

                tool_log.append({
                    "round": rounds,
                    "tool": tool_name,
                    "args": args,
                    "result": (
                        tool_result[:2000]
                        if isinstance(tool_result, str)
                        else tool_result
                    ),
                })

                # Send tool result back to model
                result = await _chat_api(
                    anon_id, model_id,
                    tool_result,
                    parent_id,
                    "tool_call_result",
                    tool_call_id,
                    tool_defs_json,
                    True,
                )

                if result.get("message_id"):
                    parent_id = result["message_id"]

        # Build response
        item: dict[str, Any] = {
            "prompt": prompt,
            "response": result.get("content", ""),
            "model": result.get("model", model_id),
        }

        if result.get("thinking"):
            item["thinking"] = result["thinking"]
        if result.get("thread_id"):
            item["thread_id"] = result["thread_id"]
        if result.get("message_id"):
            item["message_id"] = result["message_id"]
        if result.get("finish_reason"):
            item["finish_reason"] = result["finish_reason"]
        if tool_log:
            item["tool_calls"] = json.dumps(tool_log)

        return ScrapeResult(items=[item])

    async def _list_models(self) -> ScrapeResult:
        """Fetch available models from the API."""
        result = await _http_get_json(f"{API_BASE}/v4/models/")

        items = []
        for model in result:
            if not model.get("is_visible") or model.get("is_deprecated"):
                continue
            items.append({
                "title": model.get("name", ""),
                "id": model.get("id", ""),
                "family": model.get("family_id", ""),
                "type": model.get("model_type", ""),
                "description": model.get("description", ""),
                "can_think": model.get("can_think", False),
                "can_call_tools": model.get("can_call_tools", False),
                "accepts_files": model.get("accepts_files", False),
            })

        return ScrapeResult(items=items)
