"""
계좌번호를 암호화·복호화.
키는 설정 ACCOUNT_ENCRYPTION_KEY(Fernet)에서만 읽고, 화면에는 끝 4자리만 보여 줍니다.
local에서 키가 비어 있으면 고정된 개발용 키를 쓰며, 운영에서는 설정 검증이 키를 반드시 요구합니다.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.config import get_settings

_DEV_KEY_SEED = b"dole-guide-ai-local-dev-only"


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().account_encryption_key
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(_DEV_KEY_SEED).digest()).decode()
    return Fernet(key)


def encrypt(value: str) -> bytes:
    return _fernet().encrypt(value.encode("utf-8"))


def decrypt(token: bytes) -> str:
    return _fernet().decrypt(token).decode("utf-8")


def last4(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits[-4:]
