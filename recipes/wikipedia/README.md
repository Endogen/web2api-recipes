# Wikipedia

Search and read articles from [Wikipedia](https://en.wikipedia.org).

## Endpoints

| Endpoint | Description |
|---|---|
| `search` | Search articles by keyword |
| `article` | Get full article content by title |

## Usage

```
GET /wikipedia/search?q=machine learning
GET /wikipedia/article?q=Python_(programming_language)
```

### Search Response

Each result includes:

- `title` — article title
- `url` — full article URL
- `snippet` — text excerpt with matching terms

### Article Response

Returns a structured article with `title`, `url`, `summary`, `sections`, and,
when available, `infobox`, `table_of_contents`, `categories`, and
`languages_available`. Structured values are serialized by Web2API into JSON
strings in the scalar response field map.

## Pagination

Search results use page-based requests backed by Wikipedia's `limit` and
`offset` parameters. Changing `count` also changes the page stride, so results
do not overlap.

## Requirements

- No API key needed
- No environment variables required
