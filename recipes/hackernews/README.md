# Hacker News

Browse and search [Hacker News](https://news.ycombinator.com) front page stories.

## Endpoints

| Endpoint | Description |
|---|---|
| `read` | Front page stories |
| `search` | Search stories via Algolia |

## Usage

```
GET /hackernews/read?page=1
GET /hackernews/search?q=rust programming
```

### Response Fields

Each story includes:

- `title` — story title
- `url` — link to the story
- `score` — upvote count
- `author` — submitter username
- `comment_count` — number of comments
- `time_ago` — relative time
- `id` — Hacker News item ID

## Pagination

- `read` — page-based (`page=1`, `page=2`, ...)
- `search` — zero-indexed pages via Algolia (`page=0`, `page=1`, ...)

## Requirements

- No API key needed
- No environment variables required
