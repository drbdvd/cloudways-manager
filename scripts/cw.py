#!/usr/bin/env python3
"""
cw.py - thin, dependency-free Cloudways Platform API client.

Used by the `cloudways-manager` skill. Standard library only (urllib), so it
runs unchanged in the Claude sandbox, on a VPS, or in CI.

Credentials come from the environment - never hardcode them, never print them:
    export CLOUDWAYS_EMAIL="you@example.com"
    export CLOUDWAYS_API_KEY="..."          # account-level secret; treat like a root password

Auth model: POST email+api_key to /oauth/access_token -> short-lived bearer token
(~3600s). The token is cached in /tmp (0600) so a whole session of calls costs one
auth round-trip and stays under the 100 req/min rate limit.

API version: defaults to v2 (v1 hit end-of-life 2026-03-31). Override with
--api-version v1 or CW_API_VERSION=v1 if your key still serves v1.

Examples:
    python cw.py token                       # verify auth (prints OK, not the token)
    python cw.py servers                      # parsed inventory of every server + app
    python cw.py health                       # status sweep across all servers/apps
    python cw.py get server                    # raw GET /server
    python cw.py get app/manage/fpm_setting server_id=12345 app_id=67890
    python cw.py post app/manage/cache server_id=12345 app_id=67890   # clear cache
    python cw.py op 9876543                    # poll an async operation by id
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_CACHE = os.environ.get("CW_TOKEN_CACHE", "/tmp/cw_token.json")
DEFAULT_VERSION = os.environ.get("CW_API_VERSION", "v2")
TIMEOUT = 60
# Cloudflare in front of api.cloudways.com returns 403/1010 for the default
# "Python-urllib" agent. Send a normal browser-like UA so calls are not blocked.
USER_AGENT = os.environ.get(
    "CW_USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 cloudways-manager/1.0",
)


def base_url(version):
    return "https://api.cloudways.com/api/%s" % version


def _creds():
    email = os.environ.get("CLOUDWAYS_EMAIL")
    key = os.environ.get("CLOUDWAYS_API_KEY")
    if not email or not key:
        sys.exit(
            "ERROR: CLOUDWAYS_EMAIL and CLOUDWAYS_API_KEY must be set in the "
            "environment. Do not hardcode them."
        )
    return email, key


def _try_json(raw):
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw": raw}


def get_token(version, force=False):
    if not force and os.path.exists(TOKEN_CACHE):
        try:
            with open(TOKEN_CACHE) as fh:
                c = json.load(fh)
            if c.get("version") == version and c.get("expires_at", 0) > time.time() + 60:
                return c["access_token"]
        except Exception:
            pass
    email, key = _creds()
    url = base_url(version) + "/oauth/access_token"
    data = urllib.parse.urlencode({"email": email, "api_key": key}).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Accept": "application/json",
                                          "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        sys.exit("AUTH FAILED (%s): %s" % (e.code, detail))
    except urllib.error.URLError as e:
        sys.exit("NETWORK ERROR contacting Cloudways: %s" % e.reason)
    token = body.get("access_token")
    if not token:
        sys.exit("AUTH FAILED: no access_token in response: %s" % json.dumps(body)[:200])
    expires_at = time.time() + int(body.get("expires_in", 3600))
    with open(TOKEN_CACHE, "w") as fh:
        json.dump({"access_token": token, "expires_at": expires_at, "version": version}, fh)
    os.chmod(TOKEN_CACHE, 0o600)
    return token


def call(method, path, version, params=None, retry_auth=True):
    """One API call. Cloudways takes parameters as query string for GET and POST."""
    token = get_token(version)
    url = base_url(version) + "/" + path.lstrip("/")
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json",
               "User-Agent": USER_AGENT}
    req = urllib.request.Request(url, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return _try_json(resp.read().decode(errors="replace"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        # 400/401 => token likely expired/invalid; refresh once and retry.
        if e.code in (400, 401) and retry_auth:
            get_token(version, force=True)
            return call(method, path, version, params, retry_auth=False)
        return {"_http_status": e.code, "_error": True, "body": _try_json(raw)}
    except urllib.error.URLError as e:
        return {"_error": True, "reason": str(e.reason)}


def _kv(pairs):
    out = {}
    for p in pairs:
        if "=" not in p:
            sys.exit("Bad param '%s' (expected key=value)" % p)
        k, v = p.split("=", 1)
        out[k] = v
    return out


def cmd_token(args):
    get_token(args.api_version, force=True)
    print("AUTH OK (api %s). Token cached at %s" % (args.api_version, TOKEN_CACHE))


def cmd_servers(args):
    data = call("GET", "server", args.api_version)
    servers = data.get("servers") if isinstance(data, dict) else None
    if servers is None:
        print(json.dumps(data, indent=2))
        return
    for s in servers:
        print("=" * 72)
        print("SERVER %s  [%s]  %s  %s/%s  status=%s" % (
            s.get("id"), s.get("label"), s.get("public_ip"),
            s.get("cloud"), s.get("region"), s.get("status")))
        print("  size=%s  platform=%s  master_user=%s" % (
            s.get("size"), s.get("platform"), s.get("master_user")))
        apps = s.get("apps") or []
        for a in apps:
            print("    APP %s  [%s]  %s %s  user=%s  cname=%s" % (
                a.get("id"), a.get("label"), a.get("application"),
                a.get("app_version") or "", a.get("sys_user"), a.get("cname") or "-"))
    print("=" * 72)
    print("Total servers: %d" % len(servers))


def cmd_health(args):
    """Best-effort status sweep. Lists inventory, flags anything not running,
    and attempts a monitor summary per server (silently skips if unavailable)."""
    data = call("GET", "server", args.api_version)
    servers = data.get("servers") if isinstance(data, dict) else None
    if servers is None:
        print(json.dumps(data, indent=2))
        return
    flags = []
    for s in servers:
        sid = s.get("id")
        if str(s.get("status")).lower() not in ("running", "active", "live", "1", "true"):
            flags.append("Server %s (%s) status=%s" % (sid, s.get("label"), s.get("status")))
        summary = call("GET", "server/monitor/summary", args.api_version,
                       {"server_id": sid})
        line = "Server %s [%s] %s" % (sid, s.get("label"), s.get("public_ip"))
        if isinstance(summary, dict) and not summary.get("_error"):
            content = summary.get("content") or summary
            line += "  monitor=%s" % json.dumps(content)[:240]
        else:
            line += "  monitor=unavailable"
        print(line)
        for a in (s.get("apps") or []):
            print("    APP %s [%s] %s %s" % (
                a.get("id"), a.get("label"), a.get("application"), a.get("app_version") or ""))
    print("-" * 72)
    if flags:
        print("ATTENTION:")
        for f in flags:
            print("  - " + f)
    else:
        print("All servers report a running status.")


def cmd_get(args):
    print(json.dumps(call("GET", args.path, args.api_version, _kv(args.params)), indent=2))


def cmd_post(args):
    print(json.dumps(call("POST", args.path, args.api_version, _kv(args.params)), indent=2))


def cmd_put(args):
    print(json.dumps(call("PUT", args.path, args.api_version, _kv(args.params)), indent=2))


def cmd_delete(args):
    print(json.dumps(call("DELETE", args.path, args.api_version, _kv(args.params)), indent=2))


def cmd_op(args):
    print(json.dumps(call("GET", "operation/%s" % args.id, args.api_version), indent=2))


def main():
    p = argparse.ArgumentParser(description="Cloudways API client")
    p.add_argument("--api-version", default=DEFAULT_VERSION,
                   help="v2 (default) or v1")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("token").set_defaults(func=cmd_token)
    sub.add_parser("servers").set_defaults(func=cmd_servers)
    sub.add_parser("health").set_defaults(func=cmd_health)

    for name, fn in (("get", cmd_get), ("post", cmd_post),
                     ("put", cmd_put), ("delete", cmd_delete)):
        sp = sub.add_parser(name)
        sp.add_argument("path")
        sp.add_argument("params", nargs="*")
        sp.set_defaults(func=fn)

    sp = sub.add_parser("op")
    sp.add_argument("id")
    sp.set_defaults(func=cmd_op)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
