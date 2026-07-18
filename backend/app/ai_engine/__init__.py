import shutil

from .. import crypto
from ..config import settings
from ..settings_store import get_setting
from .anthropic_api import AnthropicAPIProvider
from .base import AIProvider, ExtractionError
from .claude_cli import ClaudeCLIProvider
from .codex_cli import CodexCLIProvider


def _claude_cli() -> AIProvider | None:
    return ClaudeCLIProvider() if shutil.which("claude") else None


def _codex_cli() -> AIProvider | None:
    return CodexCLIProvider() if shutil.which("codex") else None


def _anthropic_api() -> AIProvider | None:
    encrypted_key = get_setting("anthropic_api_key_encrypted")
    api_key = crypto.decrypt(encrypted_key) if encrypted_key else settings.anthropic_api_key
    return AnthropicAPIProvider(api_key) if api_key else None


def get_provider() -> AIProvider:
    # settings table (Settings UI) overrides the env-configured default
    mode = get_setting("ai_provider_mode", settings.ai_provider_mode)

    if mode == "claude_cli":
        provider = _claude_cli()
    elif mode == "codex_cli":
        provider = _codex_cli()
    elif mode == "anthropic_api":
        provider = _anthropic_api()
    else:
        provider = _claude_cli() or _codex_cli() or _anthropic_api()

    if provider is None:
        raise ExtractionError(
            "Ziadny AI provider nie je k dispozicii - nainstaluj/prihlas sa do "
            "claude alebo codex CLI, alebo nastav Anthropic API kluc v Nastaveniach"
        )
    return provider
