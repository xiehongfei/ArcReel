---
id: service-management
title: Service Lifecycle and Operations Scripts
sidebar_position: 3
update_docs: fact-check
---

# Service Lifecycle and Operations Scripts {#service-management}

This page covers the start/stop script for local development services and a quick reference for managing the production deployment. See [Deployment and Operations](deployment.md) for deployment configuration, upgrades, backups, and restoration, and [Migrating from SQLite to PostgreSQL](migrate-to-postgres.md) for the migration.

## Local Development: scripts/dev.py {#dev-script}

`scripts/dev.py` manages the backend and frontend started from source: services run in the background, and their PIDs, start times, and logs live under `.dev/`. The script uses only the standard library and runs directly, so it needs neither `uv` nor the project venv (Python 3.9+). It can be called from any directory; the working directory is derived from the script location. It relies on POSIX process-group signals and therefore supports macOS, Linux, and WSL2 only.

### Commands {#dev-script-commands}

| Command | Purpose |
| --- | --- |
| `./scripts/dev.py help` | List all commands and options |
| `./scripts/dev.py setup` | First-time setup: `uv sync`, `pnpm install`, generate `.env`, `alembic upgrade head`, install git hooks; safe to re-run |
| `./scripts/dev.py start [service]` | Start services in the background; `service` is `backend`, `frontend`, or `all` (default); returns after the ports are ready |
| `./scripts/dev.py stop [service]` | Stop services: SIGTERM first, SIGKILL after the grace period |
| `./scripts/dev.py restart [service]` | Stop, then start |
| `./scripts/dev.py status` | Show run status, ports, URLs, and readiness probes |
| `./scripts/dev.py logs [-f] [-n lines] [service]` | Show the last lines of the log (80 by default); `-f` follows new lines, Ctrl-C to exit |
| `./scripts/dev.py doctor` | Check uv, node, and pnpm versions, `.env`, dependency directories, and port conflicts |

When `.env` is missing, `setup` and `start` copy it from `.env.example`, leaving `AUTH_PASSWORD` empty so that it is generated automatically on first start.

### Options {#dev-script-options}

- `start --timeout seconds`: how long to wait for readiness, 60 by default; 0 returns right after launching.
- `stop --timeout seconds`: SIGTERM grace period, 10 by default.
- `restart --timeout seconds`: how long to wait for readiness after restarting, 60 by default.
- `stop --force`: skip the process identity check and force the stop; `restart --force` applies to the stop phase only.

### Runtime Files and Ports {#dev-script-files}

- State is written to `.dev/run/`, recording the PID, process group, and start time; `status` and `stop` read this state.
- Logs are appended to `.dev/logs/`, one file per service; when `logs -f` follows multiple services, the `[backend]` and `[frontend]` prefixes identify the source.
- Ports: backend `1241`, frontend `5173`. `.dev/` is in `.gitignore` and is not committed.

When a port is held by another process, the script reports the owning PID and gives up starting instead of killing that process; before stopping, it verifies the process identity with `ps` and refuses to stop on a mismatch. Exit codes: 0 success, 1 check or operation failed (for example, not all services are running), 2 usage error.

## Production Deployment: Docker Compose {#production-compose}

Manage the production deployment with Docker Compose from the `deploy/` (SQLite) or `deploy/production/` (PostgreSQL) directory:

| Operation | Command |
| --- | --- |
| Start | `docker compose up -d` |
| Check status | `docker compose ps` |
| View logs | `docker compose logs --tail=100 arcreel` |
| Follow logs | `docker compose logs -f arcreel` |
| Restart | `docker compose restart arcreel` |
| Stop and remove containers | `docker compose down` |

See [Deployment and Operations](deployment.md) for the complete instructions on health checks, upgrades, and data persistence, including the [health checks and logs](deployment.md#health-and-logs) section for inspection and troubleshooting commands.
