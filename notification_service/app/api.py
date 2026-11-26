import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import CurrentUser, current_user
from .db import get_session
from .schemas import AdminNotificationOut, NotificationOut
from .service import NotificationService

router = APIRouter(prefix="/v1")


def get_service(session: AsyncSession = Depends(get_session)) -> NotificationService:
    return NotificationService(session)


@router.get("/notifications/my", response_model=list[NotificationOut])
async def my_notifications(
    limit: int = Query(50, ge=1, le=200),
    svc: NotificationService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return await svc.list_mine(user, limit)


@router.get("/admin/notifications", response_model=list[AdminNotificationOut])
async def admin_list(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    svc: NotificationService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return await svc.list_admin(user, status, limit)


@router.post(
    "/admin/notifications/{notification_id}/retry", response_model=AdminNotificationOut
)
async def admin_retry(
    notification_id: uuid.UUID,
    svc: NotificationService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return await svc.retry(user, notification_id)
