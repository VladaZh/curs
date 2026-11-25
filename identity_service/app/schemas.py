import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

PHONE_RE = r"^\+[1-9]\d{6,14}$"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, pattern=PHONE_RE)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str = Field(max_length=200)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: str | None
    role: str
    restaurant_id: uuid.UUID | None
    is_active: bool


class MePatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, pattern=PHONE_RE)


class AdminCreateUser(RegisterIn):
    role: Literal["guest", "staff", "admin"] = "staff"
    restaurant_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _staff_needs_restaurant(self):
        if self.role == "staff" and self.restaurant_id is None:
            raise ValueError("Для staff нужен restaurant_id")
        return self


class AdminPatchUser(BaseModel):
    role: Literal["guest", "staff", "admin"] | None = None
    restaurant_id: uuid.UUID | None = None
    is_active: bool | None = None
