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


def get_provider_chain() -> list[AIProvider]:
    """Candidate providers in priority order. In "auto" mode this is more than
    one entry, so a caller (ingest.pipeline) can fall through to the next
    provider if one fails at call time (e.g. usage limits hit), not just at
    detection time."""
    mode = get_setting("ai_provider_mode", settings.ai_provider_mode)

    if mode == "claude_cli":
        candidates = [_claude_cli()]
    elif mode == "codex_cli":
        candidates = [_codex_cli()]
    elif mode == "anthropic_api":
        candidates = [_anthropic_api()]
    else:
        candidates = [_claude_cli(), _codex_cli(), _anthropic_api()]

    return [p for p in candidates if p is not None]


def get_provider() -> AIProvider:
    chain = get_provider_chain()
    if not chain:
        raise ExtractionError(
            "Ziadny AI provider nie je k dispozicii - nainstaluj/prihlas sa do "
            "claude alebo codex CLI, alebo nastav Anthropic API kluc v Nastaveniach"
        )
    return chain[0]
