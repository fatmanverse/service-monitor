import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from cryptography.fernet import Fernet

from .config import Settings


PBKDF2_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt), int(iterations)
        )
        return hmac.compare_digest(base64.b64encode(digest).decode(), expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, token_version: int, settings: Settings) -> str:
    expires_at = datetime.utcnow() + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": str(user_id), "ver": token_version, "exp": expires_at},
        settings.app_secret,
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: Settings) -> tuple[int, int]:
    payload = jwt.decode(token, settings.app_secret, algorithms=["HS256"])
    return int(payload["sub"]), int(payload["ver"])


class SecretCipher:
    def __init__(self, secret: str):
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        self.fernet = Fernet(key)

    def encrypt(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return self.fernet.decrypt(value.encode()).decode()
