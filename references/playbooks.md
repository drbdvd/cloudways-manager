# Cloudways diagnostic playbooks

Each playbook: read first, interpret the numbers, then pull a specific lever. Always
resolve `server_id`/`app_id` via `cw.py servers` first and echo the human-readable
labels before acting.

---

## 1. Performance / slowness debugging

**Read**
1. `cw.py health` for a fast fleet status.
2. Server monitor detail for the suspect server: idle CPU, RAM, disk, MySQL
   connections, over 1h and 7d (`get server/monitor/detail server_id=.. target=.. duration=..`).
3. App monitor detail for the suspect app: PHP, DB, disk, crons.
4. `get app/manage/fpm_setting server_id=.. app_id=..` to see the current PHP-FPM pool.

**Interpret**
- Idle CPU trending under ~20% sustained = CPU-bound. RAM near full with swap =
  memory-bound. MySQL connections pinned near the cap = DB contention.
- PHP-FPM: if `pm.max_children` is being hit (requests queue), throughput collapses
  under load even with CPU/RAM headroom.
- Disk near full silently degrades MySQL and PHP temp writes - check it even when
  CPU/RAM look fine.

**Levers**
- PHP-FPM: raise `pm.max_children` only if RAM allows (estimate per-worker MB from
  RAM/used workers); tune `pm.start_servers` / `pm.min/max_spare_servers`; lower
  `request_terminate_timeout` to shed stuck workers. Edit the pool block, POST it
  back, restart php-fpm via `/service/state`.
- Cache: ensure Varnish is on for cacheable apps; purge after deploys via
  `/app/manage/cache`. Object cache (Redis/Memcached) for WP/Magento DB load.
- Crons: heavy crons firing on the minute are a classic latency spike - move them
  off-peak and enable the cron optimizer toggle.
- DB: high connections -> raise max_connections (server settings) AND fix the query
  pattern (hand off to SSH/slow-query log for the actual offending query).
- If one server hosts too many busy apps, the real fix is splitting apps across
  servers or scaling the server size - flag this, the API tuning only goes so far.

**Speculative (flagged):** with ~20 sites on one server, the dominant slowness cause
is usually one noisy neighbour app, not global undersizing. Rank apps by PHP/DB
usage first and treat the top one before resizing the whole server.

---

## 2. Bot attacks / suspicious traffic

v2 removed the dedicated Malcare Bot Protection endpoints. Use analytics + security.

**Read**
1. `get app/monitor/analytics server_id=.. app_id=.. type=<ip_requests> duration=1h`
   - top IPs by request count.
2. Same with bot-traffic, URL-requests, and status-code types - look for one IP or
   small range dominating, a single URL (often `xmlrpc.php`, `wp-login.php`,
   `/?s=` search, or a GraphQL/admin path) being hammered, and a spike in 4xx/5xx.

**Interpret**
- A handful of IPs with order-of-magnitude more requests than the rest = scrape or
  brute force. Concentrated hits on login/xmlrpc = credential attack. A flood of
  unique IPs on one expensive URL = layer-7 DDoS / scraping via proxies.

**Levers**
- Block offending IPs/ranges via the Security Suite allow/deny list.
- Disable XML-RPC and harden the targeted endpoint (toggle + app-level rule).
- Put Cloudflare in front (Cloudways has a Cloudflare add-on) and rate-limit the
  abused path; IP blocking at the edge beats blocking at origin.
- For search/`?s=` or expensive query floods, cache or disable the feature and add a
  WAF rule - a code/config fix, not just an IP ban.

**Boundary:** the API gives aggregated top-IP/bot data, not raw log lines. To prove
intent and craft a precise WAF/code rule, pull the actual access log over **SSH**
(`grep` the offending IP/path, check user agents and request bodies). Use the API to
find *who/what*, SSH for the *exact requests*.

---

## 3. Security hardening

**Read**: SSH access state per app, HTTPS enforcement, XML-RPC state, master user,
existing IP lists.

**Levers (confirm each before applying):**
- Turn off app-level SSH where not needed; rotate master credentials if exposed.
- Enforce HTTPS on every public app.
- Disable XML-RPC on WordPress unless a known integration needs it.
- Maintain a deny list for known-bad IPs; allow-list admin IPs for sensitive apps.
- Confirm backups are enabled with a sane frequency before any risky change.

---

## 4. Stack / package updates

**Read**: `get /packages` for valid `package_name`/`package_version`; current
versions from the inventory/server settings.

**Do (with confirmation - these can cause a brief restart):**
1. Snapshot/backup first.
2. `post server/manage/package server_id=.. package_name=.. package_version=..`.
3. Poll `op <operation_id>` to completion.
4. Re-check app health; for PHP major bumps, verify each app still parses (watch for
   deprecations in app code - flag a code review for big jumps like 7.x -> 8.x).

---

## 5. Website health sweep (find the non-optimal sites)

1. `cw.py health` for status + per-server monitor summary.
2. For each app, pull app monitor summary and note PHP time, DB load, error-status
   share, disk.
3. Rank apps into a simple table: app | server | PHP load | DB load | 5xx share |
   cache on? | PHP version. Flag rows that are outliers on any axis.
4. Output a prioritized list: "these N sites are sub-optimal because X; fix Y."
   Don't just dump metrics - end with the ranked action list.

---

## 6. PHP / app configuration changes

- PHP version & limits (memory_limit, max_execution_time, upload size): server/app
  settings endpoints. Read current -> change one thing -> verify.
- PHP-FPM pool: `/app/manage/fpm_setting` (see playbook 1).
- Varnish on/off + purge; object cache; CORS, WebP, device detection, cron optimizer
  toggles as needed for the app type.
- After any PHP/FPM change, restart the relevant service and confirm the app
  responds (HTTP check) before reporting done.

---

## 7. Log & traffic review -> concrete code changes

**What the API gives:** aggregated analytics - top IPs, bot traffic, URL request
counts, HTTP status-code distribution, resource graphs.

**What needs SSH:** raw Apache/Nginx access logs, PHP error logs, slow-query logs -
i.e. the exact lines behind a 500, the stack trace, the slow SQL.

**Workflow that turns logs into code changes:**
1. API analytics -> identify the failing/slow URL and its status mix.
2. SSH (user's `ssh` or Claude Code with SSH) -> grep that URL in access+error logs,
   read the stack trace / slow query.
3. Map to code: an N+1 query, a missing index, an uncached expensive endpoint, a
   fatal on a specific input, a plugin/library bug.
4. Propose the specific fix (the query rewrite, the index DDL, the cache wrapper, the
   input guard) and, if cache-related, purge via the API after deploy.

State clearly when you're crossing from API (aggregate) to SSH (line-level) so the
user knows which tool is doing what.
