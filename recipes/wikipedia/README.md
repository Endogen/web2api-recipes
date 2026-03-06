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

Returns the full article text content.

## Pagination

Search results use offset-based pagination (`offset=0`, `offset=20`, ...).

## Requirements

- No API key needed
- No environment variables required
