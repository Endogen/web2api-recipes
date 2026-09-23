# X (Twitter)

Retrieve recent posts from an [X/Twitter](https://x.com) user profile.

## Endpoints

| Endpoint | Description |
|---|---|
| `posts` | Get recent posts by username |

## Usage

```
GET /x/posts?q=elonmusk
```

### Response

Returns a list of posts, each with:

- `text` — post content
- `author` / `author_name`
- `timestamp` and canonical `url`
- `replies`, `reposts`, `likes`, and `views`
- `is_retweet`

## Requirements

- **Authentication required** — X requires login cookies for profile scraping
- Node.js 22 or newer and npm
- `bird` 0.8.0 (`npm install -g @steipete/bird@0.8.0`); the recipe metadata can
  generate this npm install step, but intentionally does not install a
  distribution's potentially outdated Node.js package
- Set the following environment variables:

| Variable | Description |
|---|---|
| `BIRD_AUTH_TOKEN` | X auth token cookie |
| `BIRD_CT0` | X CSRF token cookie |

### Getting Auth Tokens

1. Log in to x.com in your browser
2. Open DevTools → Application → Cookies
3. Copy `auth_token` → set as `BIRD_AUTH_TOKEN`
4. Copy `ct0` → set as `BIRD_CT0`

## Notes

- Tokens may expire and need periodic refresh
- Rate limits apply based on X's policies
- Credentials are passed to `bird` through its `AUTH_TOKEN` and `CT0` environment
  variables, not command-line arguments.
