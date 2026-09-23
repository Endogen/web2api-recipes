"""X (Twitter) scraper — uses bird CLI for authenticated API access."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Any

from playwright.async_api import Page
from web2api.scraper import BaseScraper, InvalidParamsError, ScrapeResult, coerce_int


def _load_auth() -> tuple[str, str]:
    """Load bird auth tokens from env or ~/.bird_auth file."""
    auth_token = os.environ.get("BIRD_AUTH_TOKEN", "")
    ct0 = os.environ.get("BIRD_CT0", "")
    if auth_token and ct0:
        return auth_token, ct0

    bird_auth_path = Path("~/.bird_auth").expanduser()
    if bird_auth_path.is_file():
        with bird_auth_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("AUTH_TOKEN="):
                    auth_token = line.split("=", 1)[1]
                elif line.startswith("CT0="):
                    ct0 = line.split("=", 1)[1]

    if not auth_token or not ct0:
        raise RuntimeError(
            "Missing X/Twitter credentials. "
            "Set BIRD_AUTH_TOKEN + BIRD_CT0 env vars or create ~/.bird_auth"
        )
    return auth_token, ct0


class Scraper(BaseScraper):
    """Fetch user tweets via the bird CLI."""

    requires_browser = False

    def supports(self, endpoint: str) -> bool:
        return endpoint == "posts"

    async def scrape(
        self,
        endpoint: str,
        page: Page | None,
        params: dict[str, Any],
    ) -> ScrapeResult:
        username = (params.get("query") or "").strip().lstrip("@")
        if not username:
            raise InvalidParamsError("missing username — pass q=<username>")

        count = coerce_int(params.get("count", 10), name="count", default=10)
        if not 1 <= count <= 50:
            raise InvalidParamsError("count must be between 1 and 50")
        auth_token, ct0 = _load_auth()

        # bird supports AUTH_TOKEN/CT0 directly. Keep credentials out of argv so
        # they do not appear in process listings or command diagnostics.
        cmd = [
            "bird",
            "user-tweets",
            username,
            "-n",
            str(count),
            "--json",
        ]
        child_env = os.environ.copy()
        child_env.update({"AUTH_TOKEN": auth_token, "CT0": ct0})

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=child_env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except (TimeoutError, asyncio.CancelledError):
            proc.kill()
            with suppress(Exception):
                await proc.wait()
            raise

        if proc.returncode != 0:
            error_msg = stderr.decode().strip()
            if "Could not find user" in error_msg or "not found" in error_msg.lower():
                raise RuntimeError(f"Account @{username} not found")
            raise RuntimeError(f"bird CLI failed: {error_msg}")

        # Parse JSON output — bird prints info lines to stderr, JSON to stdout
        raw_output = stdout.decode().strip()

        # Find the JSON array in the output (skip any non-JSON lines)
        json_start = raw_output.find("[")
        if json_start == -1:
            raise RuntimeError(f"No JSON output from bird CLI for @{username}")

        try:
            tweets_data = json.loads(raw_output[json_start:])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON output from bird for @{username}") from exc
        if not isinstance(tweets_data, list):
            raise RuntimeError(f"Unexpected JSON output from bird for @{username}")

        items: list[dict[str, Any]] = []
        for tweet in tweets_data[:count]:
            author_username = tweet.get("author", {}).get("username", username)
            items.append(
                {
                    "text": tweet.get("text", ""),
                    "author": author_username,
                    "author_name": tweet.get("author", {}).get("name", ""),
                    "timestamp": tweet.get("createdAt", ""),
                    "url": f"https://x.com/{author_username}/status/{tweet.get('id', '')}",
                    "replies": tweet.get("replyCount"),
                    "reposts": tweet.get("retweetCount"),
                    "likes": tweet.get("likeCount"),
                    "views": tweet.get("viewCount"),
                    "is_retweet": tweet.get("text", "").startswith("RT @"),
                }
            )

        return ScrapeResult(
            items=items,
            current_page=1,
            has_next=len(tweets_data) > count,
        )
