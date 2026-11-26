import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import CurrentUser
from .errors import Conflict, Forbidden, NotFound
from .models import Notification


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def list_mine(self, user: CurrentUser, limit: int) -> list[Notification]:
        q = (
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list((await self.s.scalars(q)).all())

    async def list_admin(
        self, user: CurrentUser, status: str | None, limit: int
    ) -> list[Notification]:
        self._require_admin(user)
        q = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
        if status:
            q = q.where(Notification.status == status.upper())
        return list((await self.s.scalars(q)).all())

    async def retry(
        self, user: CurrentUser, notification_id: uuid.UUID
    ) -> Notification:
        self._require_admin(user)
        n = await self.s.scalar(
            select(Notification)
            .where(Notification.id == notification_id)
            .with_for_update()
        )
        if n is None:
            raise NotFound("Уведомление не найдено")
        if n.status != "FAILED":
            raise Conflict("Повторить можно только уведомление в статусе FAILED")
        n.status, n.attempts, n.next_attempt_at, n.last_error = (
            "PENDING",
            0,
            datetime.now(timezone.utc),
            None,
        )
        await self.s.commit()
        return n

    @staticmethod
    def _require_admin(user: CurrentUser) -> None:
        if user.role != "admin":
            raise Forbidden("Только для администратора сети")
