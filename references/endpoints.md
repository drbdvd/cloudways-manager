# Cloudways API endpoint map

Base URL: `https://api.cloudways.com/api/v2` (swap `v2`->`v1` only if v2 returns
404/410 for the account). All authenticated calls send `Authorization: Bearer
<token>`. Parameters go in the **query string** for GET and POST alike (this is how
Cloudways' own client works). `server_id` and `app_id` are the universal params.

**Confidence flags**
- `[solid]` - path and params are well established; use directly.
- `[verify]` - the capability exists in the official catalog, but confirm the exact
  path/param spelling with a cheap GET or the Playground (developers.cloudways.com/play)
  before relying on it, especially before a write. Endpoint names drift between v1
  and v2; never fire a guessed write.

Most state-changing calls return an `operation_id`. Poll `GET /operation/{id}`
until the status is complete before declaring success.

---

## Auth & inventory
| Purpose | Method | Path | Params | Flag |
|---|---|---|---|---|
| Get access token | POST | `/oauth/access_token` | `email`, `api_key` | `[solid]` |
| List servers + apps (the inventory) | GET | `/server` | - | `[solid]` |

`GET /server` returns `servers[]`; each server has `id,label,public_ip,cloud,region,
size,status,platform,master_user` and an `apps[]` array
(`id,label,application,app_version,sys_user,cname`). This one call resolves every
name->id mapping you need.

## Lists (use before updates so you pick valid values)
| Purpose | Method | Path | Flag |
|---|---|---|---|
| Available packages / versions (PHP, MySQL, Redis...) | GET | `/packages` | `[verify]` |
| Providers / regions / sizes | GET | `/providers`, `/regions`, `/server_sizes` | `[verify]` |
| App versions | GET | `/app_version` | `[verify]` |

## Server management - monitoring & health
| Purpose | Method | Path | Params | Flag |
|---|---|---|---|---|
| Server monitor summary | GET | `/server/monitor/summary` | `server_id` | `[verify]` |
| Server monitor detail/graph | GET | `/server/monitor/detail` | `server_id`,`target`,`duration` | `[verify]` |
| Server settings (read) | GET | `/server/manage/settings` | `server_id` | `[verify]` |
| Server settings (write) | POST | `/server/manage/settings` | `server_id`,+fields | `[verify]` |
| Disk usage | GET | `/server/manage/diskUsage` | `server_id` | `[verify]` |
| Optimize / clean disk | POST | `/server/manage/optimizeDisk` | `server_id` | `[verify]` |

`target` for detail graphs is a metric name (e.g. idle CPU, RAM usage, disk usage,
MySQL connections); `duration` is a window (1h up to months). Confirm the exact
enum values live - they have changed across versions.

## Stack / package updates
| Purpose | Method | Path | Params | Flag |
|---|---|---|---|---|
| Update a server package | POST | `/server/manage/package` | `server_id`,`package_name`,`package_version` | `[verify]` |

Flow: `GET /packages` to see valid `package_name`/`package_version` -> confirm with
user -> POST -> poll `operation_id`. PHP version per app may instead live under
server/app settings; check both.

## Service control
| Purpose | Method | Path | Params | Flag |
|---|---|---|---|---|
| Service states | GET | `/service` | `server_id` | `[verify]` |
| Start/stop/restart a service | POST | `/service/state` | `server_id`,`service`,`state` | `[solid]` |

`service` in {apache2, nginx, mysql, varnish, memcached, redis, elasticsearch,
php-fpm/php<ver>-fpm, supervisor}; `state` in {start, stop, restart}.

## App management - PHP / cache / config
| Purpose | Method | Path | Params | Flag |
|---|---|---|---|---|
| PHP-FPM settings (read) | GET | `/app/manage/fpm_setting` | `server_id`,`app_id` | `[solid]` |
| PHP-FPM settings (write) | POST | `/app/manage/fpm_setting` | `server_id`,`app_id`,`fpm_setting` | `[solid]` |
| Varnish settings (read) | GET | `/app/manage/varnish_setting` | `server_id`,`app_id` | `[verify]` |
| Varnish enable/disable | POST | `/app/manage/varnish` | `server_id`,`app_id`,`status` | `[verify]` |
| Clear / purge app cache | POST | `/app/manage/cache` | `server_id`,`app_id` | `[verify]` |
| Cron list (read) | GET | `/app/manage/cron` | `server_id`,`app_id` | `[verify]` |
| Cron list (write) | POST | `/app/manage/cron` | `server_id`,`app_id`,`crons` | `[verify]` |
| Enforce HTTPS | POST | `/app/manage/enforce_https` | `server_id`,`app_id`,`status` | `[verify]` |
| Toggles: xmlrpc, geo_ip, direct_php, ignore_query_string, device_detection, cors_header, webp, cron_optimizer | POST | `/app/manage/<toggle>` | `server_id`,`app_id`,`status` | `[verify]` |
| SSH access state (read/write) | GET/POST | `/app/manage/ssh_access` | `server_id`,`app_id`,`status` | `[verify]` |
| Reset file permissions | POST | `/app/manage/reset_permissions` | `server_id`,`app_id` | `[verify]` |
| App credentials (read/create/update/delete) | GET/POST/PUT/DELETE | `/app/creds` | `server_id`,`app_id`,... | `[verify]` |

`fpm_setting` is the raw PHP-FPM pool block as text (pm, pm.max_children,
pm.start_servers, request_terminate_timeout, etc.). Read it first, edit the block,
post it back whole.

## Application analytics - traffic & bots (v2 path for bot work)
| Purpose | Method | Path | Params | Flag |
|---|---|---|---|---|
| App monitor summary | GET | `/app/monitor/summary` | `server_id`,`app_id` | `[verify]` |
| App monitor detail | GET | `/app/monitor/detail` | `server_id`,`app_id`,`target`,`duration` | `[verify]` |
| Traffic analytics: top IPs / bot traffic / URL requests / status codes | GET | `/app/monitor/analytics` | `server_id`,`app_id`,`type`,`duration` | `[verify]` |

This is the replacement for the deprecated v1 Malcare Bot Protection endpoints.
`type` selects IP requests / bot traffic / URL requests / status codes. Confirm the
exact path and `type` values live - this is the single most version-sensitive area.

## Security
| Purpose | Method | Path | Flag |
|---|---|---|---|
| IP allow/deny lists (Security Suite) | GET/POST/DELETE | `/security/whitelisted` (+ deny) | `[verify]` |
| Master credentials (username/password) | POST | `/server/manage/master_user`, `/server/manage/master_password` | `[verify]` |

## v1-only (deprecated, do not use on v2)
Bot Protection (Malcare): status, traffic, login traffic, bad-bots list, whitelist
IPs/bots, activation/deactivation. Removed in v2 - use Application Analytics +
Security Suite instead.

## Operations
| Purpose | Method | Path | Flag |
|---|---|---|---|
| Poll an async operation | GET | `/operation/{id}` | `[solid]` |
