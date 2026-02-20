# X (Twitter) Recipe

This recipe adds X (Twitter) endpoints to Web2API.

## Required Setup

This recipe needs authenticated X session values.

| Environment Variable | Required | What it is                        |
| -------------------- | -------- | --------------------------------- |
| `BIRD_AUTH_TOKEN`    | Yes      | Your X session `auth_token` value |
| `BIRD_CT0`           | Yes      | Your X session `ct0` value        |

Without these values, the recipe is installed but not ready.

## Install

```bash
web2api recipes catalog add x --yes
web2api recipes install x --yes
```

## Configure Credentials

### Docker Compose (recommended)

Set the variables on the web2api service:

```yaml
services:
  web2api:
    environment:
      BIRD_AUTH_TOKEN: "<your_auth_token>"
      BIRD_CT0: "<your_ct0>"
```

Then recreate/restart the service:

```bash
docker compose up -d --force-recreate web2api
```
 
### Local (non-Docker)

```bash
export BIRD_AUTH_TOKEN="<your_auth_token>"
export BIRD_CT0="<your_ct0>"
```

Start Web2API in the same shell session.

## Verify

```bash
web2api recipes doctor x
```

Expected result:

- ready=True
- no missing env entries

If running in Docker:

```bash
docker compose exec web2api web2api recipes doctor x
```

## Troubleshooting

- If you see missing env vars, the variables are not available in the runtime process/container.
- If env vars are present but requests fail, your X session values may be expired or invalid.
- After changing credentials in Docker, restart/recreate the container.

## Security Notes

- Treat BIRD_AUTH_TOKEN and BIRD_CT0 as secrets.
- Do not commit them to git.
- Rotate them if exposed.
