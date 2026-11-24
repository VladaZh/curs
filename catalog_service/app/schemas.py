import uuid
from datetime import time
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _check_tz(v: str) -> str:
    try:
        ZoneInfo(v)
    except Exception:
        raise ValueError(
            "Неизвестный часовой пояс (ожидается IANA, например Europe/Amsterdam)"
        )
    return v


class HoursIn(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = понедельник")
    opens: time
    closes: time

    @model_validator(mode="after")
    def _order(self):
        if self.opens >= self.closes:
            raise ValueError("opens должно быть раньше closes")
        return self


def _unique_weekdays(hours: list[HoursIn]) -> list[HoursIn]:
    if len({h.weekday for h in hours}) != len(hours):
        raise ValueError("Один день недели указан несколько раз")
    return hours


class HoursOut(HoursIn):
    model_config = ConfigDict(from_attributes=True)


class RestaurantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=300)
    city: str = Field(min_length=1, max_length=100)
    timezone: str
    slot_minutes: int = Field(default=90, ge=15, le=480)
    booking_horizon_days: int = Field(default=60, ge=1, le=365)
    hours: list[HoursIn] = []

    _tz = field_validator("timezone")(_check_tz)
    _wd = field_validator("hours")(_unique_weekdays)


class RestaurantPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1, max_length=300)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = None
    slot_minutes: int | None = Field(default=None, ge=15, le=480)
    booking_horizon_days: int | None = Field(default=None, ge=1, le=365)
    is_active: bool | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v):
        return _check_tz(v) if v is not None else v


class HoursReplace(BaseModel):
    hours: list[HoursIn]
    _wd = field_validator("hours")(_unique_weekdays)


class RestaurantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str
    city: str
    timezone: str
    slot_minutes: int
    booking_horizon_days: int
    is_active: bool
    hours: list[HoursOut]


class TableCreate(BaseModel):
    label: str = Field(min_length=1, max_length=32)
    capacity: int = Field(ge=1, le=30)
    zone: str | None = Field(default=None, max_length=32)


class TablePatch(BaseModel):
    capacity: int | None = Field(default=None, ge=1, le=30)
    zone: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class TableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    restaurant_id: uuid.UUID
    label: str
    capacity: int
    zone: str | None
    is_active: bool
