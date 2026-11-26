import asyncio
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import settings
from .errors import InvalidToken


class PasswordService:
    def __init__(self):
        self._ph = PasswordHasher()

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._ph.hash, password)

    async def verify(self, hashed: str, password: str) -> bool:
        try:
            await asyncio.to_thread(self._ph.verify, hashed, password)
            return True
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, hashed: str) -> bool:
        return self._ph.check_needs_rehash(hashed)


passwords = PasswordService()
DUMMY_HASH = PasswordHasher().hash("dummy-password-for-timing")


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    role: str


def create_access_token(user) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=settings.access_ttl_minutes)
    claims = {
        "sub": str(user.id),
        "role": user.role,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + ttl,
    }
    if user.restaurant_id:
        claims["restaurant_id"] = str(user.restaurant_id)
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> CurrentUser:
    try:
        c = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
        )
        return CurrentUser(uuid.UUID(c["sub"]), c.get("role", "guest"))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise InvalidToken("Недействительный токен")


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
