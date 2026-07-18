from cryptography.fernet import Fernet, InvalidToken

from .config import settings


def _fernet() -> Fernet:
    if not settings.encryption_key:
        raise RuntimeError("MUNINN_ENCRYPTION_KEY nie je nastaveny")
    return Fernet(settings.encryption_key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Neplatny alebo poskodeny sifrovany udaj") from exc
