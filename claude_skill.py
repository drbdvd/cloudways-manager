"""
claude_skill.py – Cloudways MCP server for Claude.

Exposes Cloudways management operations as Model Context Protocol (MCP) tools
so that Claude (and other MCP clients) can query and manage your Cloudways
servers and applications via natural language.

Usage
-----
1.  Set CLOUDWAYS_EMAIL and CLOUDWAYS_API_KEY in your environment or .env file.
2.  Start the server:

        python claude_skill.py

    The server listens on stdio by default (suitable for Claude Desktop and
    most MCP clients).  To run over HTTP instead:

        python claude_skill.py --transport streamable-http --port 8080

3.  Add the server to your Claude Desktop config (~/.config/claude/claude_desktop_config.json):

        {
          "mcpServers": {
            "cloudways": {
              "command": "python",
              "args": ["/path/to/claude_skill.py"],
              "env": {
                "CLOUDWAYS_EMAIL": "your@email.com",
                "CLOUDWAYS_API_KEY": "your_api_key"
              }
            }
          }
        }
"""

from __future__ import annotations

import os

import click
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from cloudways_manager import CloudwaysClient

load_dotenv()

# ---------------------------------------------------------------------------
# MCP server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Cloudways Manager",
    instructions=(
        "You are a Cloudways server management assistant. "
        "Use the available tools to list, start, stop, restart, and monitor "
        "Cloudways servers and applications on behalf of the user."
    ),
)


def _client() -> CloudwaysClient:
    """Create a CloudwaysClient from environment variables."""
    email = os.environ.get("CLOUDWAYS_EMAIL", "")
    api_key = os.environ.get("CLOUDWAYS_API_KEY", "")
    if not email or not api_key:
        raise RuntimeError(
            "CLOUDWAYS_EMAIL and CLOUDWAYS_API_KEY environment variables must be set."
        )
    return CloudwaysClient(email, api_key)


# ---------------------------------------------------------------------------
# Server tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_servers() -> list[dict]:
    """Return all Cloudways servers on the account.

    Each entry includes the server ID, label, IP address, cloud provider,
    region, size, and status.
    """
    return _client().list_servers()


@mcp.tool()
def get_server(server_id: str) -> dict:
    """Return details for a single Cloudways server.

    Args:
        server_id: The unique Cloudways server ID.
    """
    return _client().get_server(server_id)


@mcp.tool()
def start_server(server_id: str) -> dict:
    """Start a stopped Cloudways server.

    Args:
        server_id: The unique Cloudways server ID.
    """
    return _client().start_server(server_id)


@mcp.tool()
def stop_server(server_id: str) -> dict:
    """Stop a running Cloudways server.

    Args:
        server_id: The unique Cloudways server ID.
    """
    return _client().stop_server(server_id)


@mcp.tool()
def restart_server(server_id: str) -> dict:
    """Restart a Cloudways server.

    Args:
        server_id: The unique Cloudways server ID.
    """
    return _client().restart_server(server_id)


@mcp.tool()
def manage_service(server_id: str, service: str, action: str) -> dict:
    """Start, stop, or restart a service on a Cloudways server.

    Args:
        server_id: The unique Cloudways server ID.
        service: Service name, e.g. ``apache2``, ``nginx``, ``mysql``,
            ``php8.1-fpm``, ``memcached``, ``redis-server``, ``varnish``.
        action: One of ``start``, ``stop``, or ``restart``.
    """
    return _client().manage_service(server_id, service, action)


@mcp.tool()
def get_server_monitoring(
    server_id: str,
    monitor_type: str = "cpu",
    duration: str = "last_hour",
) -> dict:
    """Fetch monitoring metrics for a Cloudways server.

    Args:
        server_id: The unique Cloudways server ID.
        monitor_type: Metric to retrieve – ``cpu``, ``memory``, ``disk``,
            or ``network``. Defaults to ``cpu``.
        duration: Time window – ``last_hour``, ``last_day``, or
            ``last_week``. Defaults to ``last_hour``.
    """
    return _client().get_server_monitoring(server_id, monitor_type, duration)


# ---------------------------------------------------------------------------
# Application tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_apps(server_id: str = "") -> list[dict]:
    """Return all applications, optionally filtered by server.

    Args:
        server_id: When provided, only applications on this server are
            returned.  Leave empty to list all applications.
    """
    return _client().list_apps(server_id or None)


@mcp.tool()
def get_app(server_id: str, app_id: str) -> dict:
    """Return details for a single application.

    Args:
        server_id: The Cloudways server ID that hosts the application.
        app_id: The unique Cloudways application ID.
    """
    return _client().get_app(server_id, app_id)


@mcp.tool()
def get_app_credentials(server_id: str, app_id: str) -> dict:
    """Retrieve SSH, SFTP, and database credentials for an application.

    Args:
        server_id: The Cloudways server ID that hosts the application.
        app_id: The unique Cloudways application ID.
    """
    return _client().get_app_credentials(server_id, app_id)


@mcp.tool()
def add_domain(server_id: str, app_id: str, domain: str) -> dict:
    """Add a domain name to a Cloudways application.

    Args:
        server_id: The Cloudways server ID that hosts the application.
        app_id: The unique Cloudways application ID.
        domain: The fully-qualified domain name to add (e.g. ``example.com``).
    """
    return _client().add_domain(server_id, app_id, domain)


@mcp.tool()
def remove_domain(server_id: str, app_id: str, domain: str) -> dict:
    """Remove a domain name from a Cloudways application.

    Args:
        server_id: The Cloudways server ID that hosts the application.
        app_id: The unique Cloudways application ID.
        domain: The fully-qualified domain name to remove.
    """
    return _client().remove_domain(server_id, app_id, domain)


# ---------------------------------------------------------------------------
# Backup tools
# ---------------------------------------------------------------------------


@mcp.tool()
def create_backup(server_id: str, app_id: str) -> dict:
    """Take an on-demand backup of a Cloudways application.

    Args:
        server_id: The Cloudways server ID that hosts the application.
        app_id: The unique Cloudways application ID.
    """
    return _client().create_backup(server_id, app_id)


@mcp.tool()
def restore_backup(server_id: str, app_id: str, backup_id: str) -> dict:
    """Restore a Cloudways application from a backup snapshot.

    Args:
        server_id: The Cloudways server ID that hosts the application.
        app_id: The unique Cloudways application ID.
        backup_id: The ID of the backup snapshot to restore.
    """
    return _client().restore_backup(server_id, app_id, backup_id)


# ---------------------------------------------------------------------------
# SSH key tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_ssh_keys() -> list[dict]:
    """List all SSH public keys registered on the Cloudways account."""
    return _client().list_ssh_keys()


@mcp.tool()
def add_ssh_key(label: str, ssh_key: str) -> dict:
    """Add an SSH public key to the Cloudways account.

    Args:
        label: A human-readable name for the key.
        ssh_key: The full SSH public key string (e.g. ``ssh-rsa AAAA...``).
    """
    return _client().add_ssh_key(label, ssh_key)


@mcp.tool()
def delete_ssh_key(ssh_key_id: str) -> dict:
    """Delete an SSH key from the Cloudways account.

    Args:
        ssh_key_id: The ID of the SSH key to delete.
    """
    return _client().delete_ssh_key(ssh_key_id)


# ---------------------------------------------------------------------------
# Operation tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_operation(operation_id: str) -> dict:
    """Return the current status of a long-running Cloudways operation.

    Args:
        operation_id: The Cloudways operation ID returned by mutating calls.
    """
    return _client().get_operation(operation_id)


@mcp.tool()
def wait_for_operation(operation_id: str, timeout: int = 600) -> dict:
    """Wait for a long-running Cloudways operation to complete.

    Polls the operation status every 5 seconds until it finishes or the
    timeout is exceeded.

    Args:
        operation_id: The Cloudways operation ID.
        timeout: Maximum number of seconds to wait (default: 600).
    """
    return _client().wait_for_operation(operation_id, timeout=timeout)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--transport",
    default="stdio",
    type=click.Choice(["stdio", "streamable-http"]),
    show_default=True,
    help="MCP transport to use.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host to bind when using streamable-http transport.",
)
@click.option(
    "--port",
    default=8080,
    show_default=True,
    help="Port to listen on when using streamable-http transport.",
)
def main(transport: str, host: str, port: int) -> None:
    """Start the Cloudways MCP skill server."""
    if transport == "streamable-http":
        mcp.run(transport="streamable-http", host=host, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
