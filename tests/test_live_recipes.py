"""Opt-in live-provider smoke tests for representative recipe paths."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from web2api.main import create_app
from web2api.recipe_manager import save_manifest
from web2api.schemas import ApiResponse

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    recipes_dir = tmp_path_factory.mktemp("trusted-recipes")
    recipe_slugs: list[str] = []
    for recipe_dir in ROOT.joinpath("recipes").iterdir():
        if not (recipe_dir / "recipe.yaml").is_file():
            continue
        recipe_slugs.append(recipe_dir.name)
        (recipes_dir / recipe_dir.name).symlink_to(recipe_dir, target_is_directory=True)
    save_manifest(
        recipes_dir,
        {
            "version": 1,
            "recipes": {slug: {"trusted": True} for slug in recipe_slugs},
        },
    )

    app = create_app(recipes_dir=recipes_dir, scrape_timeout=90)
    with TestClient(app) as test_client:
        yield test_client


def _get_response(client: TestClient, path: str, **params: object) -> ApiResponse:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    payload = ApiResponse.model_validate(response.json())
    assert payload.error is None, payload.error
    return payload


def test_nvidia_model_catalog_contains_default(client: TestClient) -> None:
    response = _get_response(client, "/nvidia/models", owner="nvidia")

    model_ids = {item.fields.get("id") for item in response.items}
    assert "nvidia/nemotron-3-super-120b-a12b" in model_ids


def test_hackernews_read(client: TestClient) -> None:
    response = _get_response(client, "/hackernews/read")

    assert response.items
    assert response.items[0].title
    assert response.items[0].url


def test_wikipedia_search(client: TestClient) -> None:
    response = _get_response(client, "/wikipedia/search", q="graph theory", count=3)

    assert 1 <= len(response.items) <= 3
    assert all(item.title and item.url for item in response.items)


def test_web_reader(client: TestClient) -> None:
    response = _get_response(client, "/web-reader/read", q="https://example.com")

    assert len(response.items) == 1
    assert "Example Domain" in str(response.items[0].fields.get("text"))
