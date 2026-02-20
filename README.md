# web2api-recipes

Official recipe catalog for Web2API.

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
