import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

bearer = HTTPBearer()


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    role: str  # guest | staff | admin
    restaurant_id: uuid.UUID | None  # для staff


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> CurrentUser:
    try:
        c = jwt.decode(
            creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        rid = c.get("restaurant_id")
        return CurrentUser(
            uuid.UUID(c["sub"]), c.get("role", "guest"), uuid.UUID(rid) if rid else None
        )
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Недействительный токен")
