"""Password hashing and JWT token service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from src.settings import SecuritySettings


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")
    salt = salt or os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${base64.b64encode(salt).decode()}${base64.b64encode(derived).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256": return False
        derived = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(rounds))
        return hmac.compare_digest(derived, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False


class TokenService:
    def __init__(self, settings: SecuritySettings): self.settings = settings

    def access_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        return jwt.encode({"sub": user_id, "type": "access", "iat": now, "exp": now + timedelta(minutes=self.settings.access_token_minutes)}, self.settings.jwt_secret_key, algorithm="HS256")

    def refresh_token(self) -> str: return secrets.token_urlsafe(48)
    @staticmethod
    def token_hash(token: str) -> str: return hashlib.sha256(token.encode()).hexdigest()

    def decode_access(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self.settings.jwt_secret_key, algorithms=["HS256"])
            if payload.get("type") != "access" or not payload.get("sub"): raise ValueError("Invalid token")
            return str(payload["sub"])
        except (JWTError, ValueError) as exc:
            raise ValueError("Invalid or expired access token") from exc
