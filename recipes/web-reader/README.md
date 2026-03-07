# Web Reader

Fetch and extract readable text content from any URL using Playwright.

## Endpoints

| Endpoint | Description |
|---|---|
| `read` | Extract readable text from a webpage |

## Usage

```
GET /web-reader/read?q=https://example.com
```

The `q` parameter takes a URL. If the protocol is omitted, `https://` is assumed.

### Response Fields

- `text` — extracted readable text (max 8000 characters)
- `url` — final URL after redirects
- `title` — page title
- `truncated` — `true` if the text was cut to fit the character limit

## How It Works

1. Navigates to the URL with Playwright (headless Chromium)
2. Removes noise elements (nav, footer, ads, popups, cookie banners)
3. Extracts text from the main content area (`<article>`, `<main>`, `.content`)
4. Falls back to `<body>` if no main content container is found
5. Cleans up whitespace and truncates to 8000 characters at a sentence boundary

## MCP Tool

When exposed via the MCP server, this recipe registers as `read_webpage` — designed to pair with `web_search` for a complete browse-and-read workflow.

## Requirements

- No API key needed
- No environment variables required
