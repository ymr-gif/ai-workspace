from cryptography.fernet import Fernet

from config import INTEGRATION_SECRET

_fernet = Fernet(INTEGRATION_SECRET.encode()) if INTEGRATION_SECRET else None


def encrypt_token(plaintext: str) -> str:
    if not _fernet:
        raise RuntimeError("INTEGRATION_SECRET not configured")
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    if not _fernet:
        raise RuntimeError("INTEGRATION_SECRET not configured")
    return _fernet.decrypt(ciphertext.encode()).decode()


def fernet_ready() -> bool:
    return _fernet is not None
