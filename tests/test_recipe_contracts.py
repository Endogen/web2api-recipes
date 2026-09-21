"""Catalog-wide recipe contract tests."""

from __future__ import annotations

from pathlib import Path

import yaml
from web2api.recipe_manager import load_catalog, validate_source_recipe_dir

ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = ROOT / "recipes"


def test_every_recipe_validates_with_its_custom_scraper() -> None:
    recipe_dirs = sorted(path for path in RECIPES_DIR.iterdir() if path.is_dir())

    assert recipe_dirs
    for recipe_dir in recipe_dirs:
        assert validate_source_recipe_dir(recipe_dir, trusted=True) == recipe_dir.name


def test_catalog_covers_every_recipe_and_declares_explicit_trust() -> None:
    catalog = load_catalog(ROOT / "catalog.yaml")
    recipe_slugs = {path.name for path in RECIPES_DIR.iterdir() if path.is_dir()}

    assert set(catalog) == recipe_slugs
    assert all(isinstance(entry.get("trusted"), bool) for entry in catalog.values())


def test_custom_scraper_params_are_declared() -> None:
    for recipe_path in sorted(RECIPES_DIR.glob("*/recipe.yaml")):
        payload = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
        for endpoint in payload["endpoints"].values():
            assert "page" not in endpoint.get("params", {})
            assert "q" not in endpoint.get("params", {})
