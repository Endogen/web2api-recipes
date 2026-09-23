# web2api-recipes

Official recipe catalog for Web2API.

Recipes in this repository are validated against Web2API `0.7.x`. Custom
scrapers declare their minimum compatible runtime in `plugin.yaml`; declarative
recipes are validated directly against the current recipe schema in CI.

## Catalog

| Recipe | Integration | Extra requirements |
|---|---|---|
| Allen AI | Direct HTTP, chat/tool/file support | None |
| Brave Search | Playwright | None |
| DeepL | Playwright | None |
| Hacker News | Declarative Playwright | None |
| NVIDIA NIM | Direct HTTP | `NVIDIA_API_KEY` for chat |
| OpenStreetMap | Direct HTTP | Configured Nominatim and OSRM providers |
| Web Reader | Playwright | None |
| Wikipedia | Playwright | None |
| X | `bird` CLI | X auth cookies and Node/npm |

## Layout

- `catalog.yaml`: installable recipe index consumed by `web2api recipes catalog ...`
- `recipes/<slug>/`: recipe folder (`recipe.yaml`, optional `scraper.py`, optional `plugin.yaml`)

## Local usage

From the Web2API project root this repository is auto-detected as the default catalog source.

You can also force it explicitly:

```bash
export WEB2API_RECIPE_CATALOG_SOURCE="$(pwd)/web2api-recipes"
web2api recipes catalog list
```

Catalog entries are explicitly trusted because several recipes execute Python
custom scrapers. Only install trusted revisions, and review local changes before
using this checkout as a catalog source. Web2API still applies its outbound
network policy to browser requests and to the direct HTTP recipes in this
catalog.

## Validation

From a checkout next to the Web2API repository:

```bash
uv run --project ../web2api ruff check recipes tests
uv run --project ../web2api pytest -q
```

The deterministic suite validates every recipe and plugin contract and exercises
the custom scraper helpers without external calls. A separate scheduled/manual
workflow runs representative live smoke tests for NVIDIA, Hacker News,
Wikipedia, and Web Reader; provider-specific recipes needing credentials or
operator-owned endpoints remain deterministic-only.

## Adding or updating a recipe

1. Add or update `recipes/<slug>/recipe.yaml` and its README.
2. Add `scraper.py` only when the declarative engine cannot express the
   integration. Custom scrapers must include `plugin.yaml` with a compatible
   Web2API minimum version.
3. Declare every public custom parameter in `recipe.yaml`; `q` and `page` are
   reserved by Web2API.
4. Add the recipe to `catalog.yaml` with an explicit `trusted` value and keep
   catalog `requires_env` metadata aligned with `plugin.yaml`.
5. Add deterministic regression tests for parsing, validation, and secret
   handling. Put network-dependent checks behind the `e2e` marker.
