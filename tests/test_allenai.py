"""Behavior tests for the Allen AI custom scraper."""

from __future__ import annotations

import json

import pytest
from web2api.scraper import InvalidParamsError


def test_clean_schema_removes_defaults_recursively(load_recipe_module: object) -> None:
    module = load_recipe_module("allenai")
    schema = {
        "type": "object",
        "default": {},
        "properties": {
            "query": {"type": "string", "default": ""},
            "choice": {
                "anyOf": [
                    {"type": "string", "default": "a"},
                    {"type": "integer"},
                ]
            },
        },
    }

    cleaned = module._clean_schema(schema)

    assert "default" not in cleaned
    assert "default" not in cleaned["properties"]["query"]
    assert "default" not in cleaned["properties"]["choice"]["anyOf"][0]


def test_parse_stream_events_supports_ndjson_and_multiline(load_recipe_module: object) -> None:
    module = load_recipe_module("allenai")
    raw = (
        '{"type":"start","message":"thread-1"}\n'
        "{\n"
        '  "type": "modelResponse",\n'
        '  "content": "hello"\n'
        "}\n"
    )

    assert module._parse_stream_events(raw) == [
        {"type": "start", "message": "thread-1"},
        {"type": "modelResponse", "content": "hello"},
    ]


@pytest.mark.asyncio
async def test_fetch_tools_filters_malformed_definitions(
    load_recipe_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recipe_module("allenai")

    async def fake_get(_url: str) -> object:
        return [
            {"name": "search", "description": "Search", "parameters": {"type": "object"}},
            {"description": "missing name", "parameters": {}},
            {"name": "bad-schema", "parameters": []},
        ]

    monkeypatch.setattr(module, "_http_get_json", fake_get)

    assert await module._fetch_tools("https://tools.example/mcp") == [
        {"name": "search", "description": "Search", "parameters": {"type": "object"}}
    ]


@pytest.mark.asyncio
async def test_call_tool_encodes_name_and_rejects_non_object_args(
    load_recipe_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recipe_module("allenai")
    seen: dict[str, object] = {}

    async def fake_post(url: str, body: dict) -> object:
        seen.update(url=url, body=body)
        return {"result": {"ok": True}}

    monkeypatch.setattr(module, "_http_post_json", fake_post)

    result = await module._call_tool("https://tools.example/mcp", "search/read me", {"q": "hello"})
    invalid = await module._call_tool("https://tools.example/mcp", "search", "bad")

    assert seen == {
        "url": "https://tools.example/mcp/tools/search%2Fread%20me",
        "body": {"q": "hello"},
    }
    assert json.loads(result) == {"ok": True}
    assert "JSON object" in json.loads(invalid)["error"]


@pytest.mark.asyncio
async def test_missing_prompt_is_invalid_params(load_recipe_module: object) -> None:
    module = load_recipe_module("allenai")

    with pytest.raises(InvalidParamsError, match="missing prompt"):
        await module.Scraper().scrape("chat", None, {"query": ""})
