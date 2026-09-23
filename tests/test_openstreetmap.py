"""Behavior tests for OpenStreetMap input handling."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from web2api.scraper import InvalidParamsError


def test_parse_coords_is_strict_and_range_checked(load_recipe_module: object) -> None:
    module = load_recipe_module("openstreetmap")

    assert module._parse_coords("52.52,13.405; -33.86, 151.21") == [
        (52.52, 13.405),
        (-33.86, 151.21),
    ]

    for value in ("52,13;bad;48,2", "91,13", "52,181", "52,13;"):
        with pytest.raises(InvalidParamsError):
            module._parse_coords(value)


@pytest.mark.asyncio
async def test_nearby_search_preserves_zero_coordinates(
    load_recipe_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recipe_module("openstreetmap")
    seen: dict[str, str] = {}

    async def fake_get(url: str, *, nominatim: bool = False) -> object:
        seen.update(url=url, nominatim=str(nominatim))
        return []

    monkeypatch.setenv("NOMINATIM_BASE_URL", "https://geo.example")
    monkeypatch.setattr(module, "_get_json", fake_get)

    assert await module._search_places("cafe", lat=0.0, lon=0.0, radius=1000) == []

    query = parse_qs(urlsplit(seen["url"]).query)
    assert query["lat"] == ["0.0"]
    assert query["lon"] == ["0.0"]
    assert query["bounded"] == ["1"]
    assert "viewbox" in query


@pytest.mark.asyncio
async def test_nearby_search_requires_coordinate_pair(load_recipe_module: object) -> None:
    module = load_recipe_module("openstreetmap")

    with pytest.raises(InvalidParamsError, match="provided together"):
        await module._search_places("cafe", lat=52.5)


@pytest.mark.asyncio
async def test_reverse_requires_exactly_one_pair(load_recipe_module: object) -> None:
    module = load_recipe_module("openstreetmap")

    with pytest.raises(InvalidParamsError, match="expects one"):
        await module.Scraper().scrape("reverse", None, {"query": "52,13;48,2"})
