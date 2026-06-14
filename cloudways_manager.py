"""
Cloudways Manager – API client and CLI for managing Cloudways servers.

Usage
-----
Set CLOUDWAYS_EMAIL and CLOUDWAYS_API_KEY in the environment (or in a .env file),
then run:

    python cloudways_manager.py servers list
    python cloudways_manager.py server --id <SERVER_ID> info
    python cloudways_manager.py server --id <SERVER_ID> start
    python cloudways_manager.py server --id <SERVER_ID> stop
    python cloudways_manager.py server --id <SERVER_ID> restart
    python cloudways_manager.py server --id <SERVER_ID> service --name apache --action restart
    python cloudways_manager.py apps list [--server-id <SERVER_ID>]
    python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> info
    python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> credentials
    python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> backup
    python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> add-domain --domain example.com
    python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> remove-domain --domain example.com
    python cloudways_manager.py ssh-keys list
    python cloudways_manager.py operation --id <OP_ID> status
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import click
import requests
from dotenv import load_dotenv

load_dotenv()

CLOUDWAYS_API_URL = "https://api.cloudways.com/api/v1"

# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


class CloudwaysClient:
    """Thin wrapper around the Cloudways REST API v1."""

    def __init__(self, email: str, api_key: str) -> None:
        self.email = email
        self.api_key = api_key
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _refresh_token(self) -> None:
        resp = requests.post(
            f"{CLOUDWAYS_API_URL}/oauth/access_token",
            data={"email": self.email, "api_key": self.api_key},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        # Refresh 60 s before the token actually expires
        self._token_expires_at = time.time() + expires_in - 60

    def _get_token(self) -> str:
        if not self._token or time.time() >= self._token_expires_at:
            self._refresh_token()
        return self._token  # type: ignore[return-value]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer " + self._get_token()}

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        resp = requests.get(
            f"{CLOUDWAYS_API_URL}/{path}",
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        resp = requests.post(
            f"{CLOUDWAYS_API_URL}/{path}",
            headers=self._headers(),
            data=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        resp = requests.put(
            f"{CLOUDWAYS_API_URL}/{path}",
            headers=self._headers(),
            data=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        resp = requests.delete(
            f"{CLOUDWAYS_API_URL}/{path}",
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Server management
    # ------------------------------------------------------------------

    def list_servers(self) -> list[dict[str, Any]]:
        """Return all servers on the account."""
        return self._get("server").get("servers", [])

    def get_server(self, server_id: str) -> dict[str, Any]:
        """Return a single server by ID."""
        for srv in self.list_servers():
            if srv.get("id") == server_id:
                return srv
        raise ValueError(f"Server '{server_id}' not found")

    def start_server(self, server_id: str) -> dict[str, Any]:
        return self._post(
            "server/service/action",
            {"server_id": server_id, "service": "MASTER", "action": "start"},
        )

    def stop_server(self, server_id: str) -> dict[str, Any]:
        return self._post(
            "server/service/action",
            {"server_id": server_id, "service": "MASTER", "action": "stop"},
        )

    def restart_server(self, server_id: str) -> dict[str, Any]:
        return self._post(
            "server/service/action",
            {"server_id": server_id, "service": "MASTER", "action": "restart"},
        )

    def manage_service(self, server_id: str, service: str, action: str) -> dict[str, Any]:
        """Start, stop or restart a service on the server.

        Common service names: ``apache2``, ``nginx``, ``mysql``,
        ``php8.1-fpm``, ``memcached``, ``redis-server``, ``varnish``,
        ``elasticsearch``.
        Common actions: ``start``, ``stop``, ``restart``.
        """
        return self._post(
            "server/service/action",
            {"server_id": server_id, "service": service, "action": action},
        )

    def get_server_monitoring(
        self,
        server_id: str,
        monitor_type: str = "cpu",
        duration: str = "last_hour",
    ) -> dict[str, Any]:
        """Return monitoring data for a server.

        ``monitor_type`` options: ``cpu``, ``memory``, ``disk``, ``network``.
        ``duration`` options: ``last_hour``, ``last_day``, ``last_week``.
        """
        return self._get(
            "server/monitor/summary",
            {"server_id": server_id, "type": monitor_type, "duration": duration},
        )

    # ------------------------------------------------------------------
    # Application management
    # ------------------------------------------------------------------

    def list_apps(self, server_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Return all applications, optionally filtered by ``server_id``."""
        apps: list[dict[str, Any]] = self._get("app").get("apps", [])
        if server_id:
            apps = [a for a in apps if a.get("server_id") == server_id]
        return apps

    def get_app(self, server_id: str, app_id: str) -> dict[str, Any]:
        """Return a single application by server ID and app ID."""
        for app in self.list_apps(server_id):
            if app.get("id") == app_id:
                return app
        raise ValueError(f"App '{app_id}' not found on server '{server_id}'")

    def get_app_credentials(self, server_id: str, app_id: str) -> dict[str, Any]:
        return self._get(
            "app/manage/credentials",
            {"server_id": server_id, "app_id": app_id},
        )

    def add_domain(self, server_id: str, app_id: str, domain: str) -> dict[str, Any]:
        return self._post(
            "app/manage/addDomain",
            {"server_id": server_id, "app_id": app_id, "domain": domain},
        )

    def remove_domain(self, server_id: str, app_id: str, domain: str) -> dict[str, Any]:
        return self._post(
            "app/manage/removeDomain",
            {"server_id": server_id, "app_id": app_id, "domain": domain},
        )

    # ------------------------------------------------------------------
    # Backup management
    # ------------------------------------------------------------------

    def create_backup(self, server_id: str, app_id: str) -> dict[str, Any]:
        """Trigger an on-demand backup for an application."""
        return self._post(
            "app/manage/takeBackup",
            {"server_id": server_id, "app_id": app_id},
        )

    def restore_backup(
        self,
        server_id: str,
        app_id: str,
        backup_id: str,
    ) -> dict[str, Any]:
        """Restore an application from a backup snapshot."""
        return self._post(
            "app/manage/restoreBackup",
            {"server_id": server_id, "app_id": app_id, "backup_id": backup_id},
        )

    # ------------------------------------------------------------------
    # SSH key management
    # ------------------------------------------------------------------

    def list_ssh_keys(self) -> list[dict[str, Any]]:
        return self._get("ssh_key").get("ssh_keys", [])

    def add_ssh_key(self, label: str, ssh_key: str) -> dict[str, Any]:
        return self._post("ssh_key/add", {"label": label, "ssh_key": ssh_key})

    def delete_ssh_key(self, ssh_key_id: str) -> dict[str, Any]:
        return self._delete("ssh_key", {"id": ssh_key_id})

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def get_operation(self, operation_id: str) -> dict[str, Any]:
        """Return the current status of a long-running Cloudways operation."""
        return self._get(f"operation/{operation_id}")

    def wait_for_operation(
        self,
        operation_id: str,
        poll_interval: int = 5,
        timeout: int = 600,
    ) -> dict[str, Any]:
        """Block until an operation finishes (status 1 = success, 2 = failed)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self.get_operation(operation_id)
            status = result.get("operation", {}).get("status")
            if status in ("1", "2", 1, 2):
                return result
            time.sleep(poll_interval)
        raise TimeoutError(
            f"Operation {operation_id} did not complete within {timeout} s"
        )


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _make_client() -> CloudwaysClient:
    email = os.environ.get("CLOUDWAYS_EMAIL", "")
    api_key = os.environ.get("CLOUDWAYS_API_KEY", "")
    if not email or not api_key:
        raise click.ClickException(
            "CLOUDWAYS_EMAIL and CLOUDWAYS_API_KEY must be set in the environment "
            "or in a .env file."
        )
    return CloudwaysClient(email, api_key)


def _print_json(data: Any) -> None:
    click.echo(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Manage your Cloudways servers and applications from the command line."""


# ── servers ─────────────────────────────────────────────────────────────────


@cli.group()
def servers() -> None:
    """List all servers on the account."""


@servers.command("list")
def servers_list() -> None:
    """Print all servers as JSON."""
    _print_json(_make_client().list_servers())


# ── server ──────────────────────────────────────────────────────────────────


@cli.group()
@click.option("--id", "server_id", required=True, help="Cloudways server ID")
@click.pass_context
def server(ctx: click.Context, server_id: str) -> None:
    """Commands that target a single server."""
    ctx.ensure_object(dict)
    ctx.obj["server_id"] = server_id
    ctx.obj["client"] = _make_client()


@server.command("info")
@click.pass_context
def server_info(ctx: click.Context) -> None:
    """Show details for the server."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(client.get_server(ctx.obj["server_id"]))


@server.command("start")
@click.pass_context
def server_start(ctx: click.Context) -> None:
    """Start the server."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(client.start_server(ctx.obj["server_id"]))


@server.command("stop")
@click.pass_context
def server_stop(ctx: click.Context) -> None:
    """Stop the server."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(client.stop_server(ctx.obj["server_id"]))


@server.command("restart")
@click.pass_context
def server_restart(ctx: click.Context) -> None:
    """Restart the server."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(client.restart_server(ctx.obj["server_id"]))


@server.command("service")
@click.option("--name", required=True, help="Service name (e.g. apache2, nginx, mysql)")
@click.option(
    "--action",
    required=True,
    type=click.Choice(["start", "stop", "restart"]),
    help="Action to perform",
)
@click.pass_context
def server_service(ctx: click.Context, name: str, action: str) -> None:
    """Start, stop or restart a service on the server."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(client.manage_service(ctx.obj["server_id"], name, action))


@server.command("monitor")
@click.option(
    "--type",
    "monitor_type",
    default="cpu",
    type=click.Choice(["cpu", "memory", "disk", "network"]),
    show_default=True,
)
@click.option(
    "--duration",
    default="last_hour",
    type=click.Choice(["last_hour", "last_day", "last_week"]),
    show_default=True,
)
@click.pass_context
def server_monitor(ctx: click.Context, monitor_type: str, duration: str) -> None:
    """Display monitoring data for the server."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(
        client.get_server_monitoring(ctx.obj["server_id"], monitor_type, duration)
    )


# ── apps ────────────────────────────────────────────────────────────────────


@cli.group()
def apps() -> None:
    """List applications."""


@apps.command("list")
@click.option("--server-id", default=None, help="Filter by server ID")
def apps_list(server_id: Optional[str]) -> None:
    """Print all applications as JSON."""
    _print_json(_make_client().list_apps(server_id))


# ── app ─────────────────────────────────────────────────────────────────────


@cli.group()
@click.option("--server-id", required=True, help="Cloudways server ID")
@click.option("--app-id", required=True, help="Cloudways application ID")
@click.pass_context
def app(ctx: click.Context, server_id: str, app_id: str) -> None:
    """Commands that target a single application."""
    ctx.ensure_object(dict)
    ctx.obj["server_id"] = server_id
    ctx.obj["app_id"] = app_id
    ctx.obj["client"] = _make_client()


@app.command("info")
@click.pass_context
def app_info(ctx: click.Context) -> None:
    """Show details for the application."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(client.get_app(ctx.obj["server_id"], ctx.obj["app_id"]))


@app.command("credentials")
@click.pass_context
def app_credentials(ctx: click.Context) -> None:
    """Fetch SSH/SFTP/DB credentials for the application."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(
        client.get_app_credentials(ctx.obj["server_id"], ctx.obj["app_id"])
    )


@app.command("backup")
@click.pass_context
def app_backup(ctx: click.Context) -> None:
    """Take an on-demand backup of the application."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(client.create_backup(ctx.obj["server_id"], ctx.obj["app_id"]))


@app.command("restore")
@click.option("--backup-id", required=True, help="ID of the backup snapshot to restore")
@click.pass_context
def app_restore(ctx: click.Context, backup_id: str) -> None:
    """Restore the application from a backup snapshot."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(
        client.restore_backup(ctx.obj["server_id"], ctx.obj["app_id"], backup_id)
    )


@app.command("add-domain")
@click.option("--domain", required=True, help="Domain name to add")
@click.pass_context
def app_add_domain(ctx: click.Context, domain: str) -> None:
    """Add a domain to the application."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(
        client.add_domain(ctx.obj["server_id"], ctx.obj["app_id"], domain)
    )


@app.command("remove-domain")
@click.option("--domain", required=True, help="Domain name to remove")
@click.pass_context
def app_remove_domain(ctx: click.Context, domain: str) -> None:
    """Remove a domain from the application."""
    client: CloudwaysClient = ctx.obj["client"]
    _print_json(
        client.remove_domain(ctx.obj["server_id"], ctx.obj["app_id"], domain)
    )


# ── ssh-keys ────────────────────────────────────────────────────────────────


@cli.group("ssh-keys")
def ssh_keys() -> None:
    """Manage SSH keys on the account."""


@ssh_keys.command("list")
def ssh_keys_list() -> None:
    """List all SSH keys."""
    _print_json(_make_client().list_ssh_keys())


@ssh_keys.command("add")
@click.option("--label", required=True, help="Human-readable label for the key")
@click.option("--key", "ssh_key", required=True, help="Public key string")
def ssh_keys_add(label: str, ssh_key: str) -> None:
    """Add a new SSH public key to the account."""
    _print_json(_make_client().add_ssh_key(label, ssh_key))


@ssh_keys.command("delete")
@click.option("--id", "ssh_key_id", required=True, help="ID of the SSH key to delete")
def ssh_keys_delete(ssh_key_id: str) -> None:
    """Delete an SSH key from the account."""
    _print_json(_make_client().delete_ssh_key(ssh_key_id))


# ── operation ────────────────────────────────────────────────────────────────


@cli.group()
def operation() -> None:
    """Check the status of a Cloudways operation."""


@operation.command("status")
@click.option("--id", "operation_id", required=True, help="Operation ID")
def operation_status(operation_id: str) -> None:
    """Print the current status of a long-running operation."""
    _print_json(_make_client().get_operation(operation_id))


@operation.command("wait")
@click.option("--id", "operation_id", required=True, help="Operation ID")
@click.option("--timeout", default=600, show_default=True, help="Timeout in seconds")
def operation_wait(operation_id: str, timeout: int) -> None:
    """Block until a long-running operation completes."""
    _print_json(_make_client().wait_for_operation(operation_id, timeout=timeout))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
