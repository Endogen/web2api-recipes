# Brave Search

Web search via [Brave Search](https://search.brave.com) — extracts organic results with titles, URLs, and snippets.

## Endpoints

| Endpoint | Description |
|---|---|
| `search` | Web search (requires query) |

## Usage

```
GET /brave-search/search?q=python web scraping&page=1
```

### Response

Returns a list of search results, each with:

- `title` — result title
- `url` — result URL
- `snippet` — description text

## Pagination

Uses offset-based pagination via the `offset` query parameter (starts at 0).

## Requirements

- No API key needed — scrapes Brave Search directly
- No environment variables required
