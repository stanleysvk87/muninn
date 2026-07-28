from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MUNINN_", env_file=".env", extra="ignore")

    data_dir: Path = Path("./data")
    archive_dir: Path = Path("./archive")
    db_path: Path = Path("./data/muninn.db")

    # Only read by the docker-compose port mapping and by the systemd unit's
    # ExecStart (both via the env file) -- the app itself never binds a port,
    # uvicorn does.
    port: int = 8000
    cors_origins: str = ""
    # Hard ceiling for a single uploaded file. Uploads are staged in /tmp
    # (boot volume), not on the archive volume, so an unbounded upload could
    # fill the system disk.
    max_upload_mb: int = 100
    frontend_dist_dir: Path = Path("../frontend/dist")

    encryption_key: str = ""
    # Optional fixed token for /api/auth/bootstrap. Leave empty to have one
    # generated into data_dir/bootstrap-token.txt on first use (see
    # auth/security.bootstrap_token).
    bootstrap_token: str = ""
    session_ttl_days: int = 7
    cookie_secure: bool = True

    ai_provider_mode: str = "auto"  # auto | claude_cli | codex_cli | anthropic_api
    anthropic_api_key: str = ""

    # NOTE: mail/IMAP ingestion is configured exclusively in the app
    # (Settings -> Mail, stored in the settings table with the password
    # Fernet-encrypted, see ingest/mail_ingest.py). There are deliberately no
    # MUNINN_MAIL_* settings here: the fields that used to sit at this spot
    # were read by nothing at all, so following the old .env.example meant
    # writing an IMAP password in plaintext to disk for a poller that then
    # silently never started.

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.archive_dir.mkdir(parents=True, exist_ok=True)
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
