"""Behavior tests for Wikipedia URL and pagination handling."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from web2api.scraper import InvalidParamsError


def test_article_slug_accepts_title_and_wikipedia_url(load_recipe_module: object) -> None:
    module = load_recipe_module("wikipedia")

    assert module._article_slug("Python (programming language)") == (
        "Python_(programming_language)"
    )
    assert (
        module._article_slug("https://en.wikipedia.org/wiki/Python_(programming_language)#History")
        == "Python_(programming_language)"
    )

    with pytest.raises(InvalidParamsError, match="en.wikipedia.org"):
        module._article_slug("https://example.com/wiki/Python")


@pytest.mark.asyncio
async def test_search_count_controls_limit_and_page_stride(
    load_recipe_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recipe_module("wikipedia")

    class Page:
        url = ""

        async def goto(self, url: str, **_kwargs: object) -> None:
            self.url = url

        async def wait_for_selector(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def query_selector(self, selector: str) -> object | None:
            return object() if selector == ".mw-nextlink" else None

    extract = AsyncMock(return_value=[])
    monkeypatch.setattr(module.Scraper, "_extract_search_results", extract)
    page = Page()

    result = await module.Scraper()._search(page, {"query": "graph theory", "count": 7, "page": 3})

    assert "search=graph%20theory" in page.url
    assert "limit=7" in page.url
    assert "offset=14" in page.url
    assert result.current_page == 3
    assert result.has_next is True
    extract.assert_awaited_once_with(page, 7)
