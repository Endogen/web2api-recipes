"""Shared helpers for loading standalone recipe scraper modules."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def load_recipe_module() -> object:
    cache: dict[str, ModuleType] = {}

    def _load(slug: str) -> ModuleType:
        if slug in cache:
            return cache[slug]
        path = ROOT / "recipes" / slug / "scraper.py"
        spec = importlib.util.spec_from_file_location(
            f"_web2api_recipe_test_{slug.replace('-', '_')}",
            path,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cache[slug] = module
        return module

    return _load
