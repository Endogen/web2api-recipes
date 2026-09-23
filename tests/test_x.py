"""Behavior and secret-handling tests for the X recipe."""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_bird_credentials_are_not_exposed_in_argv(
    load_recipe_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recipe_module("x")
    seen: dict[str, object] = {}

    class Process:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            payload = [
                {
                    "id": "123",
                    "text": "hello",
                    "author": {"username": "alice", "name": "Alice"},
                    "likeCount": 4,
                }
            ]
            return json.dumps(payload).encode(), b""

    async def fake_subprocess(*args: str, **kwargs: object) -> Process:
        seen.update(args=args, kwargs=kwargs)
        return Process()

    monkeypatch.setattr(module, "_load_auth", lambda: ("secret-auth", "secret-ct0"))
    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", fake_subprocess)

    result = await module.Scraper().scrape("posts", None, {"query": "@alice", "count": 10})

    args = seen["args"]
    child_env = seen["kwargs"]["env"]
    assert "secret-auth" not in args
    assert "secret-ct0" not in args
    assert child_env["AUTH_TOKEN"] == "secret-auth"
    assert child_env["CT0"] == "secret-ct0"
    assert result.items[0]["url"] == "https://x.com/alice/status/123"
