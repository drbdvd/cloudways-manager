# Cloudways Manager

A small, dependency-free Python client for the Cloudways Platform API, plus a Claude
skill for diagnosing and operating Cloudways servers and apps: performance debugging,
bot/traffic analysis, security, stack updates, health checks, and PHP/app config.

Standard library only — no `pip install` needed. Works on macOS, Linux, and in CI.

## Requirements

- Python 3 (`python3` on macOS)
- A Cloudways **account-owner** API key (team-member keys don't have API access)

## Setup: export your credentials

Credentials are read from environment variables. They are never stored in the repo.

```bash
export CLOUDWAYS_EMAIL="your-cloudways-login@email.com"
export CLOUDWAYS_API_KEY="your-api-key"
```

`export` lasts only for the current terminal window. Open a new terminal and you
re-run these two lines. To set them permanently, add the two lines to `~/.zshrc`
(macOS default shell), then `source ~/.zshrc`.

Get / regenerate the key in the Cloudways Platform: bottom-left menu → **API
Integration** → **Generate / Regenerate Key**.

> The API key has account-level power (same as the account owner). Treat it like a
> root password. Never paste it into chat, never commit it.

## Quick start

```bash
python3 scripts/cw.py token      # verify auth — prints "AUTH OK", never the token
python3 scripts/cw.py servers    # list every server and app with IDs and status
python3 scripts/cw.py health     # status sweep across the whole fleet
```

If `token` prints `AUTH OK`, you're set.

## Commands

| Command | What it does |
|---|---|
| `token` | Verify credentials and cache a bearer token |
| `servers` | Parsed inventory: each server + its apps, with IDs and status |
| `health` | Status sweep; flags anything not running |
| `get <path> [k=v ...]` | Raw GET against any endpoint |
| `post <path> [k=v ...]` | Raw POST (state-changing — see warning below) |
| `put <path> [k=v ...]` | Raw PUT |
| `delete <path> [k=v ...]` | Raw DELETE |
| `op <operation_id>` | Poll an async operation until it finishes |

`server_id` and `app_id` are the parameters you'll reuse everywhere. Get them once
from `servers`.

Examples:

```bash
# read PHP-FPM settings for one app
python3 scripts/cw.py get app/manage/fpm_setting server_id=12345 app_id=67890

# clear an app's cache (state-changing)
python3 scripts/cw.py post app/manage/cache server_id=12345 app_id=67890

# poll the operation it returned
python3 scripts/cw.py op 98765432
```

## API version

Defaults to **v2** (`https://api.cloudways.com/api/v2`). Cloudways API v1 reached
end-of-life on 2026-03-31. If a call 404s on v2, retry with v1 to check access:

```bash
python3 scripts/cw.py --api-version v1 servers
```

## Read before you write

Default to read-only (`get`, `servers`, `health`). Before any `post/put/delete`
(restarts, package updates, setting changes, deletes), know which `server_id` /
`app_id` you're hitting — many writes cause brief downtime or are irreversible.

Rate limit: **100 requests/minute**.

## Using it with Claude

Two ways:

1. **Manual:** run a command locally and paste the **output** into Claude. The output
   contains no secrets, so it's safe. Claude interprets it and gives you the next
   command.
2. **Hands-off (Claude Code):** install Claude Code (`npm install -g
   @anthropic-ai/claude-code`), run `claude` inside this folder, and ask in plain
   language ("check my server health", "which sites are slow?"). It runs `cw.py` for
   you, on your machine, where your exported keys live.

## Optional environment variables

| Variable | Default | Purpose |
|---|---|---|
| `CW_API_VERSION` | `v2` | Override the API version |
| `CW_TOKEN_CACHE` | `/tmp/cw_token.json` | Where the bearer token is cached |
| `CW_USER_AGENT` | browser-like UA | Sent to get past Cloudflare's default-agent block |

## Security notes

- Never commit secrets. Add a `.gitignore` with at least:
  ```
  .env
  *.env
  cw_token.json
  ```
- The bearer token caches to `/tmp` (outside the repo) with `0600` permissions.
- If a key is ever exposed (pasted in chat, committed, etc.), regenerate it.

## Files

```
cloudways-manager/
├── README.md
├── SKILL.md                  # Claude skill: when to use, safety, routing
├── scripts/
│   └── cw.py                 # the API client
└── references/
    ├── endpoints.md          # endpoint map per job, with confidence flags
    └── playbooks.md          # diagnostic workflows for each use case
```
