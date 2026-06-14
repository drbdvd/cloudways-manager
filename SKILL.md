---
name: cloudways-manager
description: >-
  Manage, diagnose, and operate Cloudways-hosted servers and applications through
  the Cloudways Platform API. Use this skill WHENEVER the user mentions Cloudways,
  a Cloudways server/app, or asks to debug site performance/slowness, investigate
  bot attacks or suspicious traffic, harden security, run stack/package updates,
  check the health of their websites, find which sites are underperforming, adjust
  PHP / PHP-FPM / Varnish / app settings, clear caches, restart services, review
  traffic analytics or logs, or manage crons, domains, SSL, and backups on
  Cloudways - even if they don't say the word "API". The skill handles OAuth token
  exchange, picks the right endpoint, and turns raw responses into actionable
  findings and concrete config/code changes.
---

# Cloudways Manager

Operate a Cloudways fleet over the Platform API: performance debugging, bot-attack
and security investigation, stack updates, health checks, PHP/app config tuning,
and log/traffic analysis that leads to specific config or code changes.

## Before anything else: credentials & safety

The API key has **account-level power** - it can rebuild, delete, and re-credential
servers, the same as the account owner. Treat it like a root password.

1. Credentials live in environment variables only. Never hardcode them, never write
   them to a file, never echo them, never put them in memory:
   ```bash
   export CLOUDWAYS_EMAIL="owner@example.com"
   export CLOUDWAYS_API_KEY="..."
   ```
   If they are not set, ask the user to set them for this session. If a user pastes a
   key into chat, tell them to regenerate it afterwards (Platform menu -> API
   Integration -> Regenerate Key) because it has been exposed.
2. **Read before write.** Default to GET/diagnostic calls. Before any state-changing
   call (POST/PUT/DELETE - restarts, package updates, setting changes, password
   resets, deletes), state plainly what it will do and which `server_id`/`app_id` it
   targets, and get explicit confirmation. Many writes are irreversible or cause
   brief downtime.
3. **Rate limit: 100 requests/minute.** The client caches the bearer token; still
   batch and avoid tight polling loops.
4. Verify the target. With ~20 sites on one account, always echo the resolved
   server label + app label before acting, not just numeric IDs.

## The client

All calls go through `scripts/cw.py` (standard-library Python, no install needed).
It handles OAuth, token caching, version selection, and error envelopes.

```bash
python scripts/cw.py token        # verify auth (prints OK, never the token)
python scripts/cw.py servers      # parsed inventory: every server + app + status
python scripts/cw.py health       # status sweep across the whole fleet
python scripts/cw.py get  <path> [k=v ...]    # generic GET
python scripts/cw.py post <path> [k=v ...]    # generic POST (state-changing)
python scripts/cw.py put|delete <path> [k=v ...]
python scripts/cw.py op <operation_id>        # poll an async operation
```

`server_id` and `app_id` are the universal parameters. Get them once from
`servers`, reuse everywhere. Most write calls return an `operation_id`; poll it with
`op <id>` until status is complete before reporting success.

## API version (important)

Default base URL is **`/api/v2`**. Cloudways **API v1 reached end-of-life on
2026-03-31**; v2 is the same OAuth flow and mostly the same paths (literally `v1` ->
`v2` in the URL). If a call returns 404/410 on v2, retry the same call with
`--api-version v1` to check whether the account still has v1 access, and tell the
user which version is actually serving them.

**v2 deprecation that matters here:** the dedicated **Bot Protection (Malcare)**
endpoints from v1 were removed in v2. For bot/abuse work in v2 use **Application
Analytics (Traffic)** + the **Security Suite** allow/deny lists instead. See
`references/playbooks.md` -> Bot attacks.

## How to work a request

1. **Resolve targets first.** Run `servers` (or reuse a known inventory) to map the
   user's site name -> `server_id` + `app_id`.
2. **Pick the endpoint.** Consult `references/endpoints.md`. It marks each endpoint
   with a confidence level. For anything marked *verify*, confirm the exact
   path/params with a cheap GET (or the API Playground at
   developers.cloudways.com/play) before relying on it - prefer a live read over a
   guessed write.
3. **Diagnose with reads**, then **propose** specific changes with confidence, then
   **execute writes** only after confirmation.
4. **Translate findings into action.** Don't stop at "CPU is high." Tie it to a
   concrete lever: a PHP-FPM `max_children` change, a Varnish/cache toggle, a cron
   that should be moved off-peak, an IP to block, or a code path to fix.

## Use-case playbooks

For each of the core jobs, follow the matching section in
`references/playbooks.md`:

- **Performance / slowness debugging** - monitor graphs, PHP-FPM + Varnish tuning,
  cron and DB pressure, disk.
- **Bot attacks / suspicious traffic** - traffic analytics (top IPs, bot traffic,
  status codes), then Security Suite allow/deny + Cloudflare; SSH for raw log lines.
- **Security hardening** - SSH access state, HTTPS enforcement, XML-RPC, master
  credentials, IP lists.
- **Stack / package updates** - inventory current versions, update server packages
  (PHP, MySQL/MariaDB, Redis, etc.), verify via operation polling.
- **Website health sweep** - `health` plus per-app analytics to rank sites and flag
  the non-optimal ones.
- **PHP / app configuration** - FPM settings, server settings (PHP version, limits),
  Varnish, cache, CORS, WebP, cron optimizer.
- **Log & traffic review -> code changes** - what the API exposes (aggregated
  analytics) vs. what needs SSH (raw access/error logs), and how to turn either into
  a code recommendation.

## Honest capability boundary

The Platform API exposes **aggregated** monitoring and traffic analytics and all
configuration controls. It does **not** stream raw Apache/Nginx/PHP access or error
log lines. For per-request forensics ("show me the exact 500s and their stack
traces", "grep the access log for this path") the user needs **SSH** (their own
`ssh` or Claude Code with the server's SSH credentials). Say so rather than
pretending the API can do it, and hand off cleanly: use the API to find *which*
server/app and *what* to look for, then SSH for the line-level evidence.

## References

- `references/endpoints.md` - endpoint map grouped by job, with parameters and a
  confidence flag per entry. Read this before composing any non-trivial call.
- `references/playbooks.md` - step-by-step diagnostic workflows for each use case
  above, including which numbers indicate a problem and which lever fixes it.
