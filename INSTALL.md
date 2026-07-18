# Installation

Two independent deployment paths — pick one. Both use the same code (one
process serves API and frontend, no nginx/Caddy), the same data directory
(SQLite DB + file archive), and the same environment variables from
`.env.example`. Both have been verified end-to-end (Docker via
`docker compose up` + bootstrap/upload/restart/persistence; the systemd
unit passes `systemd-analyze verify`), including on two different physical
machines across two different CPU architectures (aarch64 and x86_64).

## Prerequisites (both paths)

- Linux (tested on Debian/Ubuntu-based and Armbian aarch64).
- Generate `MUNINN_ENCRYPTION_KEY` (used to encrypt the mail password,
  Telegram bot token, and Anthropic API key at rest) once, and put it in
  your env file — never commit it to git:
  ```
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- Decide on an AI engine: an existing `claude`/`codex` CLI login (no extra
  billing, but tied to a specific user's home directory), or an Anthropic
  API key (independent of any user account, better suited to a hardened
  dedicated service account). See "AI provider chain" in
  [ARCHITECTURE.md](ARCHITECTURE.md).

## A) Docker

```
cp .env.example .env
# edit .env: MUNINN_ENCRYPTION_KEY (required), MUNINN_PORT, and optionally
# MUNINN_DATA_HOST_PATH / MUNINN_ARCHIVE_HOST_PATH if you don't want ./data and ./archive
docker compose up -d
```

- One container (`docker ps` shows only `muninn-muninn-1`), no extra
  nginx/Caddy.
- The data and archive directories are mounted via `.env`
  (`MUNINN_DATA_HOST_PATH` / `MUNINN_ARCHIVE_HOST_PATH`, defaulting to
  `./data` and `./archive`) — not hardcoded in `docker-compose.yml`.
- To use the CLI AI engine instead of an API key, set
  `MUNINN_CLAUDE_BIN_HOST_PATH` (and/or `MUNINN_CODEX_BIN_HOST_PATH`) in
  `.env` to the CLI binary's real path on the host, so it can be
  bind-mounted in read-only alongside your `~/.claude`/`~/.codex` config.
  This only works if the container runs on the same CPU architecture as
  the host (the CLI binary isn't portable across architectures).
- Two more mounts (a shared `CLAUDE.md` location, and a drop-zone watch
  folder) are also host-configurable via env vars — see the comments in
  `docker-compose.yml`. Leave them unset and they default to small local
  placeholder directories instead of touching anything outside the
  project directory.
- Verified: `docker compose up -d` → `curl localhost:8000/api/health` →
  200, bootstrap the first account via `POST /api/auth/bootstrap`, upload
  a document, `docker compose restart` → both the session and the
  document survived (SQLite lives on the bind-mounted volume, not in the
  container layer).

## B) systemd (no Docker)

```
python3 -m venv /opt/muninn/backend/venv
/opt/muninn/backend/venv/bin/pip install -r backend/requirements.txt
# copy backend/app to /opt/muninn/backend/app

cd frontend && npm install && npm run build
# copy frontend/dist to /opt/muninn/frontend/dist

sudo mkdir -p /etc/muninn
sudo cp systemd/muninn.env.example /etc/muninn/muninn.env
sudo chmod 600 /etc/muninn/muninn.env
# edit /etc/muninn/muninn.env: MUNINN_ENCRYPTION_KEY (required)

sudo cp systemd/muninn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now muninn
```

- Runs as a plain process under `uvicorn`, `Type=simple`,
  `Restart=on-failure`.
- The unit file passes `systemd-analyze verify` (the only message you'll
  see is the expected "binary not found" one, until `/opt/muninn` actually
  exists).
- **Important**: if the app uses the `claude`/`codex` CLI as its AI
  engine, the service must run as your own logged-in user, not a
  dedicated hardened service account — the CLI credentials live in that
  specific user's `~/.claude`. If you want a dedicated service account
  with full isolation (`NoNewPrivileges`, `ProtectSystem=strict`, ...),
  use an API key instead of the CLI — see the commented-out block in
  `systemd/muninn.service`.

## Mail ingestion (optional, either deployment path)

The app works fine without this — mail polling is disabled by default. To
enable automatic processing of mail attachments (and HTML/plain-text mail
bodies that arrive with no attachment at all):

1. Create a mailbox on an existing mail server (outside this repo), e.g.
   `docker exec mailserver setup email add invoices@yourdomain.example <password>`.
2. In the app, under Settings → Mail, enable it and enter the IMAP
   credentials.

## Watch folder

Under Settings → Folders, add the path to a folder the app should watch
(e.g. a folder synced via Syncthing from your phone). The change takes
effect immediately, no restart needed. Existing files already sitting in
a folder when it's (re)registered are picked up too, not just new ones
arriving afterward.

## Telegram alerts (optional)

Under Settings → Telegram alerts, enter a bot token (create one via
[@BotFather](https://t.me/BotFather)) and the chat ID that should receive
expiry/renewal reminders. The bot token is encrypted at rest.
