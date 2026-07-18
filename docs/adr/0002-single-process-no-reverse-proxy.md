# ADR 0002: Single process, no nginx/Caddy

## Context

Heimdall runs as 3 containers (backend, frontend+nginx, optional Caddy
for TLS). Muninn's requirement, though, is to be deployable equally
easily as a Docker container or a systemd service on any Linux host — the
more moving parts (a reverse proxy, multiple containers), the harder that
is to replicate outside Docker.

## Decision

The FastAPI backend directly serves the built React frontend too
(`StaticFiles` + a catch-all route for SPA fallback + GZip middleware +
cache headers for hashed assets). One process, one port.

## Consequences

- Docker deployment: 1 container instead of 3.
- systemd deployment: 1 unit file, `uvicorn main:app`, no extra nginx
  config.
- Anyone who wants TLS termination can put their own reverse proxy in
  front of the app (the same way Heimdall's optional Caddy profile
  works) — that's outside the app itself, not part of it.
- `--workers 1` (not more) is required — the watch-folder observer and
  the mail poller run in the same process as the web server; more
  workers would mean the same events get processed multiple times.
