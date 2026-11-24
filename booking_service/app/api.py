import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db import get_session
from app.schemas import BookingOut, CreateBookingIn, FreeTableOut, StatusChangeIn
from app.service import BookingService

router = APIRouter(prefix="/v1")


def get_service(session: AsyncSession = Depends(get_session)) -> BookingService:
    return BookingService(session)


@router.get("/availability", response_model=list[FreeTableOut])
async def availability(
    restaurant_id: uuid.UUID,
    starts_at: datetime,
    party_size: int = Query(ge=1, le=20),
    svc: BookingService = Depends(get_service),
    _: CurrentUser = Depends(current_user),
):
    tables = await svc.free_tables(restaurant_id, svc.period_for(starts_at), party_size)
    return [FreeTableOut(table_id=t.id, capacity=t.capacity) for t in tables]


@router.post("/bookings", response_model=BookingOut, status_code=201)
async def create_booking(
    body: CreateBookingIn,
    idempotency_key: str | None = Header(None, max_length=64),
    svc: BookingService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    b = await svc.create_hold(
        user, body.restaurant_id, body.starts_at, body.party_size, idempotency_key
    )
    return BookingOut.from_orm_booking(b)


@router.get("/bookings/my", response_model=list[BookingOut])
async def my_bookings(
    svc: BookingService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return [BookingOut.from_orm_booking(b) for b in await svc.list_mine(user)]


@router.get("/bookings/{booking_id}", response_model=BookingOut)
async def get_booking(
    booking_id: uuid.UUID,
    svc: BookingService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return BookingOut.from_orm_booking(await svc.get(user, booking_id))


@router.post("/bookings/{booking_id}/confirm", response_model=BookingOut)
async def confirm(
    booking_id: uuid.UUID,
    svc: BookingService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return BookingOut.from_orm_booking(await svc.confirm(user, booking_id))


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
async def cancel(
    booking_id: uuid.UUID,
    svc: BookingService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return BookingOut.from_orm_booking(await svc.cancel(user, booking_id))


@router.post("/staff/bookings/{booking_id}/status", response_model=BookingOut)
async def staff_status(
    booking_id: uuid.UUID,
    body: StatusChangeIn,
    svc: BookingService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return BookingOut.from_orm_booking(
        await svc.staff_set_status(user, booking_id, body.status)
    )


@router.get(
    "/staff/restaurants/{restaurant_id}/bookings", response_model=list[BookingOut]
)
async def restaurant_day(
    restaurant_id: uuid.UUID,
    day: datetime = Query(description="Начало суток, aware datetime"),
    svc: BookingService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return [
        BookingOut.from_orm_booking(b)
        for b in await svc.list_for_restaurant(user, restaurant_id, day)
    ]
