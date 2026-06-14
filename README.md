# cloudways-manager

A Python toolkit to manage your [Cloudways](https://www.cloudways.com) servers
and applications from the command line **and** via an
[MCP](https://modelcontextprotocol.io/) skill that lets
[Claude](https://claude.ai) control your infrastructure through natural
language.

---

## Contents

| File | Purpose |
|------|---------|
| `cloudways_manager.py` | Cloudways API client + `click`-based CLI |
| `claude_skill.py` | MCP server exposing Cloudways tools for Claude |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |

---

## Requirements

* Python 3.10+
* A [Cloudways](https://platform.cloudways.com) account
* Your Cloudways **API key** (Account → API section of the dashboard)

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

`.env`:

```ini
CLOUDWAYS_EMAIL=your@email.com
CLOUDWAYS_API_KEY=your_api_key_here
```

> **Never commit `.env` to source control.**

Alternatively export the variables in your shell:

```bash
export CLOUDWAYS_EMAIL=your@email.com
export CLOUDWAYS_API_KEY=your_api_key_here
```

---

## CLI usage (`cloudways_manager.py`)

### Servers

```bash
# List all servers
python cloudways_manager.py servers list

# Show details for a single server
python cloudways_manager.py server --id <SERVER_ID> info

# Start / stop / restart a server
python cloudways_manager.py server --id <SERVER_ID> start
python cloudways_manager.py server --id <SERVER_ID> stop
python cloudways_manager.py server --id <SERVER_ID> restart

# Manage a service on the server
python cloudways_manager.py server --id <SERVER_ID> service --name apache2 --action restart
python cloudways_manager.py server --id <SERVER_ID> service --name mysql   --action stop

# View monitoring data
python cloudways_manager.py server --id <SERVER_ID> monitor --type cpu --duration last_hour
```

### Applications

```bash
# List all applications (optionally filter by server)
python cloudways_manager.py apps list
python cloudways_manager.py apps list --server-id <SERVER_ID>

# Show application details
python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> info

# Fetch SSH / SFTP / DB credentials
python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> credentials

# Create an on-demand backup
python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> backup

# Restore from a backup snapshot
python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> restore --backup-id <BACKUP_ID>

# Domain management
python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> add-domain    --domain example.com
python cloudways_manager.py app --server-id <SERVER_ID> --app-id <APP_ID> remove-domain --domain example.com
```

### SSH keys

```bash
python cloudways_manager.py ssh-keys list
python cloudways_manager.py ssh-keys add    --label "My Laptop" --key "ssh-rsa AAAA..."
python cloudways_manager.py ssh-keys delete --id <KEY_ID>
```

### Operations

```bash
# Check the status of a long-running operation
python cloudways_manager.py operation status --id <OP_ID>

# Block until an operation finishes (with optional timeout)
python cloudways_manager.py operation wait --id <OP_ID> --timeout 300
```

---

## Claude skill (MCP server) usage (`claude_skill.py`)

### Add to Claude Desktop

Edit `~/.config/claude/claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "cloudways": {
      "command": "python",
      "args": ["/absolute/path/to/claude_skill.py"],
      "env": {
        "CLOUDWAYS_EMAIL": "your@email.com",
        "CLOUDWAYS_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

Restart Claude Desktop.  You can now ask Claude things like:

* *"List my Cloudways servers"*
* *"Restart the MySQL service on server abc123"*
* *"Take a backup of my WordPress app"*
* *"What is the CPU usage on my production server?"*

### Run over HTTP (for custom MCP clients)

```bash
python claude_skill.py --transport streamable-http --host 127.0.0.1 --port 8080
```

The MCP endpoint will be available at `http://127.0.0.1:8080/mcp`.

### Available tools

| Tool | Description |
|------|-------------|
| `list_servers` | List all servers on the account |
| `get_server` | Get details for a single server |
| `start_server` | Start a server |
| `stop_server` | Stop a server |
| `restart_server` | Restart a server |
| `manage_service` | Start / stop / restart a service |
| `get_server_monitoring` | Fetch CPU / memory / disk / network metrics |
| `list_apps` | List all applications |
| `get_app` | Get details for a single application |
| `get_app_credentials` | Retrieve SSH / SFTP / DB credentials |
| `add_domain` | Add a domain to an application |
| `remove_domain` | Remove a domain from an application |
| `create_backup` | Take an on-demand backup |
| `restore_backup` | Restore from a backup snapshot |
| `list_ssh_keys` | List SSH keys on the account |
| `add_ssh_key` | Add an SSH public key |
| `delete_ssh_key` | Delete an SSH key |
| `get_operation` | Get status of a long-running operation |
| `wait_for_operation` | Wait for an operation to complete |

---

## Security

* Credentials are read from environment variables or a `.env` file – never
  hard-coded.
* Add `.env` to your `.gitignore` to avoid accidental commits.
* Tokens obtained from the Cloudways API are automatically refreshed before
  expiry and kept in memory only.
