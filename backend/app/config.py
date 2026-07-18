from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MUNINN_", env_file=".env", extra="ignore")

    data_dir: Path = Path("./data")
    archive_dir: Path = Path("./archive")
    db_path: Path = Path("./data/muninn.db")

    port: int = 8000
    cors_origins: str = ""

    encryption_key: str = ""
    session_ttl_days: int = 7
    cookie_secure: bool = True

    ai_provider_mode: str = "auto"  # auto | claude_cli | codex_cli | anthropic_api
    anthropic_api_key: str = ""

    mail_enabled: bool = False
    mail_host: str = ""
    mail_port: int = 993
    mail_username: str = ""
    mail_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.archive_dir.mkdir(parents=True, exist_ok=True)
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
