import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, Field

from app.domain import BookingStatus


class CreateBookingIn(BaseModel):
    restaurant_id: uuid.UUID
    starts_at: AwareDatetime
    party_size: int = Field(ge=1, le=20)


class StatusChangeIn(BaseModel):
    status: BookingStatus


class BookingOut(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    table_id: uuid.UUID
    party_size: int
    status: BookingStatus
    starts_at: datetime
    ends_at: datetime
    expires_at: datetime | None

    @classmethod
    def from_orm_booking(cls, b) -> "BookingOut":
        return cls(
            id=b.id,
            restaurant_id=b.restaurant_id,
            table_id=b.table_id,
            party_size=b.party_size,
            status=b.status,
            starts_at=b.period.lower,
            ends_at=b.period.upper,
            expires_at=b.expires_at,
        )


class FreeTableOut(BaseModel):
    table_id: uuid.UUID
    capacity: int
