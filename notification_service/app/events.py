import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict


class _Event(BaseModel):
    model_config = ConfigDict(extra="ignore")


class UserEvent(_Event):
    user_id: uuid.UUID
    email: str
    full_name: str
    phone: str | None = None
    is_active: bool = True
    version: int


class RestaurantEvent(_Event):
    restaurant_id: uuid.UUID
    name: str
    timezone: str
    version: int


class BookingEvent(_Event):
    booking_id: uuid.UUID
    restaurant_id: uuid.UUID
    guest_id: uuid.UUID
    party_size: int
    status: str
    starts_at: AwareDatetime
    ends_at: AwareDatetime
