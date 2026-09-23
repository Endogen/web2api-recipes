"""Catalog-wide recipe contract tests."""

from __future__ import annotations

from pathlib import Path

import yaml
from web2api.execution import _coerce_param_value
from web2api.mcp_utils import build_tool_name
from web2api.recipe_loader import load_plugin_config, load_recipe_config, load_scraper
from web2api.recipe_manager import load_catalog, validate_source_recipe_dir

ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = ROOT / "recipes"


def _recipe_dirs() -> list[Path]:
    return sorted(path.parent for path in RECIPES_DIR.glob("*/recipe.yaml"))


def test_every_recipe_validates_with_its_custom_scraper() -> None:
    recipe_dirs = _recipe_dirs()

    assert recipe_dirs
    for recipe_dir in recipe_dirs:
        assert validate_source_recipe_dir(recipe_dir, trusted=True) == recipe_dir.name


def test_catalog_covers_every_recipe_and_declares_explicit_trust() -> None:
    catalog = load_catalog(ROOT / "catalog.yaml")
    recipe_slugs = {path.name for path in _recipe_dirs()}

    assert set(catalog) == recipe_slugs
    assert all(isinstance(entry.get("trusted"), bool) for entry in catalog.values())


def test_custom_scraper_params_are_declared() -> None:
    for recipe_path in sorted(RECIPES_DIR.glob("*/recipe.yaml")):
        payload = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
        for endpoint in payload["endpoints"].values():
            assert "page" not in endpoint.get("params", {})
            assert "q" not in endpoint.get("params", {})


def test_custom_scrapers_cover_every_declared_endpoint() -> None:
    for recipe_dir in _recipe_dirs():
        if not (recipe_dir / "scraper.py").exists():
            continue
        config = load_recipe_config(recipe_dir)
        scraper = load_scraper(recipe_dir, trusted=True)

        assert scraper is not None
        assert all(scraper.supports(endpoint) for endpoint in config.endpoints)


def test_custom_scrapers_declare_current_web2api_compatibility() -> None:
    for recipe_dir in _recipe_dirs():
        if not (recipe_dir / "scraper.py").exists():
            continue
        plugin = load_plugin_config(recipe_dir)

        assert plugin is not None, f"{recipe_dir.name} custom scraper has no plugin.yaml"
        assert plugin.web2api.min_version == "0.7.0"


def test_catalog_and_plugin_environment_requirements_match() -> None:
    catalog = load_catalog(ROOT / "catalog.yaml")

    for recipe_dir in _recipe_dirs():
        plugin = load_plugin_config(recipe_dir)
        plugin_env = set(plugin.requires_env if plugin is not None else [])
        catalog_env = set(catalog[recipe_dir.name].get("requires_env", []))
        assert plugin_env == catalog_env, recipe_dir.name


def test_mcp_tool_names_are_unique() -> None:
    tool_names: list[str] = []
    for recipe_dir in _recipe_dirs():
        config = load_recipe_config(recipe_dir)
        tool_names.extend(
            build_tool_name(config.slug, name, endpoint.tool_name)
            for name, endpoint in config.endpoints.items()
        )

    assert len(tool_names) == len(set(tool_names))


def test_every_recipe_documents_its_endpoints() -> None:
    for recipe_dir in _recipe_dirs():
        config = load_recipe_config(recipe_dir)
        readme = (recipe_dir / "README.md").read_text(encoding="utf-8")

        for endpoint in config.endpoints:
            assert endpoint in readme, f"{recipe_dir.name} does not document {endpoint}"


def test_parameter_examples_satisfy_their_declared_constraints() -> None:
    for recipe_dir in _recipe_dirs():
        config = load_recipe_config(recipe_dir)
        for endpoint_name, endpoint in config.endpoints.items():
            for param_name, param in endpoint.params.items():
                if param.example is None:
                    continue
                value = _coerce_param_value(param_name, str(param.example), param)
                assert value is not None, f"{recipe_dir.name}/{endpoint_name}/{param_name}"
