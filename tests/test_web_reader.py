"""Pure behavior tests for the Web Reader scraper."""

from __future__ import annotations

import pytest
from web2api.scraper import InvalidParamsError


def test_normalize_url(load_recipe_module: object) -> None:
    module = load_recipe_module("web-reader")

    assert module._normalize_url("example.com/article") == "https://example.com/article"
    assert module._normalize_url("http://example.com") == "http://example.com"
    with pytest.raises(InvalidParamsError):
        module._normalize_url("")


def test_clean_and_truncate_text(load_recipe_module: object) -> None:
    module = load_recipe_module("web-reader")
    dirty = "Heading\n\n\n\nBody   text\t\tcontinued"

    assert module._clean_text(dirty) == "Heading\n\nBody text continued"

    sentence = "A complete sentence. "
    shortened, truncated = module._truncate_text(sentence * 1000)
    assert truncated is True
    assert len(shortened) <= module.MAX_TEXT_LENGTH
    assert shortened.endswith(".")


def test_short_text_is_not_truncated(load_recipe_module: object) -> None:
    module = load_recipe_module("web-reader")

    assert module._truncate_text("short") == ("short", False)
