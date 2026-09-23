"""Behavior tests for the NVIDIA NIM custom scraper."""

from __future__ import annotations

import json

import pytest
from web2api.scraper import InvalidParamsError


@pytest.mark.asyncio
async def test_models_filters_owner_and_prefix(
    load_recipe_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recipe_module("nvidia")

    async def fake_http(*_args: object, **_kwargs: object) -> object:
        return {
            "data": [
                {"id": "nvidia/a", "owned_by": "nvidia", "object": "model"},
                {"id": "nvidia/b", "owned_by": "nvidia", "object": "model"},
                {"id": "other/c", "owned_by": "other", "object": "model"},
            ]
        }

    monkeypatch.setattr(module, "_http_json", fake_http)

    result = await module.Scraper()._models({"owner": "NVIDIA", "prefix": "nvidia/b"})

    assert [item["id"] for item in result.items] == ["nvidia/b"]


@pytest.mark.asyncio
async def test_chat_uses_current_default_and_typed_options(
    load_recipe_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recipe_module("nvidia")
    seen: dict[str, object] = {}

    async def fake_http(url: str, **kwargs: object) -> object:
        seen.update(url=url, **kwargs)
        return {
            "model": module.DEFAULT_MODEL,
            "choices": [{"message": {"content": "Hi"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 3},
        }

    monkeypatch.setattr(module, "_http_json", fake_http)

    result = await module.Scraper()._chat({"query": "Hello", "temperature": 0.2, "max_tokens": 64})

    body = seen["body"]
    assert body["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 64
    assert result.items[0]["response"] == "Hi"
    assert json.loads(result.items[0]["usage"])["total_tokens"] == 3


@pytest.mark.asyncio
async def test_chat_requires_prompt(load_recipe_module: object) -> None:
    module = load_recipe_module("nvidia")

    with pytest.raises(InvalidParamsError, match="missing prompt"):
        await module.Scraper()._chat({"query": ""})
