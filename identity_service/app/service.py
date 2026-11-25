import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.app.config import settings
from identity_service.app.errors import (AccountLocked, Conflict, Forbidden, InvalidCredentials, InvalidInput,
                                         InvalidToken, NotFound)
from identity_service.app.models import OutboxEvent, RefreshToken, User
from .schemas import AdminCreateUser, AdminPatchUser, MePatch, RegisterIn, TokenPair
from .security import (DUMMY_HASH, CurrentUser, create_access_token, hash_token, new_refresh_token,
                        passwords)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm_email(email: str) -> str:
    return email.strip().lower()


class IdentityService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def register(self, data: RegisterIn) -> User:
        return await self._create_user(data.email, data.password, data.full_name, data.phone, "guest", None)

    async def login(self, email: str, password: str) -> TokenPair:
        user = await self.s.scalar(select(User).where(User.email == _norm_email(email)).with_for_update())
        if user is None:
            await passwords.verify(DUMMY_HASH, password)
            raise InvalidCredentials("Неверный email или пароль")

        if user.locked_until and user.locked_until > _now():
            raise AccountLocked("Слишком много попыток входа, попробуйте позже")

        ok = await passwords.verify(user.password_hash, password)
        if not ok or not user.is_active:
            user.failed_attempts += 1
            if user.failed_attempts >= settings.max_failed_attempts:
                user.locked_until = _now() + timedelta(minutes=settings.lockout_minutes)
                user.failed_attempts = 0
            await self.s.commit()
            raise InvalidCredentials("Неверный email или пароль")

        user.failed_attempts, user.locked_until = 0, None
        if passwords.needs_rehash(user.password_hash):
            user.password_hash = await passwords.hash(password)
        pair = self._issue_tokens(user, family_id=uuid.uuid4())
        await self.s.commit()
        return pair

    async def refresh(self, raw_token: str) -> TokenPair:
        rt = await self.s.scalar(select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(raw_token)).with_for_update())
        if rt is None:
            raise InvalidToken("Недействительный refresh-токен")
        if rt.revoked_at is not None:
            await self._revoke_family(rt.family_id)
            await self.s.commit()
            raise InvalidToken("Refresh-токен уже использован, войдите заново")
        if rt.expires_at < _now():
            raise InvalidToken("Refresh-токен истёк")

        user = await self.s.get(User, rt.user_id)
        if user is None or not user.is_active:
            await self._revoke_family(rt.family_id)
            await self.s.commit()
            raise InvalidToken("Учётная запись отключена")

        rt.revoked_at = _now()
        pair = self._issue_tokens(user, family_id=rt.family_id)
        await self.s.commit()
        return pair

    async def logout(self, raw_token: str) -> None:
        rt = await self.s.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
        if rt is not None:
            await self._revoke_family(rt.family_id)
            await self.s.commit()

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self.s.get(User, user_id)
        if user is None or not user.is_active:
            raise NotFound("Пользователь не найден")
        return user

    async def update_me(self, actor: CurrentUser, patch: MePatch) -> User:
        user = await self._lock_user(actor.id)
        for k, v in patch.model_dump(exclude_unset=True).items():
            setattr(user, k, v)
        user.version += 1
        self._emit(user, "user.changed")
        await self.s.commit()
        return user

    async def admin_create_user(self, actor: CurrentUser, data: AdminCreateUser) -> User:
        self._require_admin(actor)
        return await self._create_user(data.email, data.password, data.full_name, data.phone,
                                       data.role, data.restaurant_id)

    async def admin_update_user(self, actor: CurrentUser, user_id: uuid.UUID, patch: AdminPatchUser) -> User:
        self._require_admin(actor)
        user = await self._lock_user(user_id)
        for k, v in patch.model_dump(exclude_unset=True).items():
            setattr(user, k, v)
        if user.role != "staff":
            user.restaurant_id = None
        elif user.restaurant_id is None:
            raise InvalidInput("Для staff нужен restaurant_id")
        if not user.is_active:
            await self._revoke_all(user.id)
        user.version += 1
        self._emit(user, "user.changed")
        await self.s.commit()
        return user

    async def resync(self, actor: CurrentUser) -> int:
        self._require_admin(actor)
        users = (await self.s.scalars(select(User))).all()
        for u in users:
            self._emit(u, "user.changed")
        await self.s.commit()
        return len(users)

    async def ensure_admin(self, email: str, password: str) -> None:
        exists = await self.s.scalar(select(User.id).where(User.email == _norm_email(email)))
        if not exists:
            await self._create_user(email, password, "Administrator", None, "admin", None)

    async def _create_user(self, email, password, full_name, phone, role, restaurant_id) -> User:
        user = User(email=_norm_email(email), password_hash=await passwords.hash(password),
                    full_name=full_name, phone=phone, role=role, restaurant_id=restaurant_id)
        self.s.add(user)
        try:
            await self.s.flush()
        except IntegrityError:
            await self.s.rollback()
            raise Conflict("Пользователь с таким email уже существует")
        self._emit(user, "user.registered")
        await self.s.commit()
        return user

    def _issue_tokens(self, user: User, family_id: uuid.UUID) -> TokenPair:
        access, expires_in = create_access_token(user)
        raw = new_refresh_token()
        self.s.add(RefreshToken(user_id=user.id, family_id=family_id, token_hash=hash_token(raw),
                                expires_at=_now() + timedelta(days=settings.refresh_ttl_days)))
        return TokenPair(access_token=access, refresh_token=raw, expires_in=expires_in)

    async def _revoke_family(self, family_id: uuid.UUID) -> None:
        await self.s.execute(update(RefreshToken).where(
            RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=_now()))

    async def _revoke_all(self, user_id: uuid.UUID) -> None:
        await self.s.execute(update(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=_now()))

    async def _lock_user(self, user_id: uuid.UUID) -> User:
        user = await self.s.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None:
            raise NotFound("Пользователь не найден")
        return user

    @staticmethod
    def _require_admin(actor: CurrentUser) -> None:
        if actor.role != "admin":
            raise Forbidden("Только для администратора сети")

    def _emit(self, u: User, topic: str) -> None:
        self.s.add(OutboxEvent(topic=topic, payload={
            "user_id": str(u.id), "email": u.email, "full_name": u.full_name, "phone": u.phone,
            "role": u.role, "restaurant_id": str(u.restaurant_id) if u.restaurant_id else None,
            "is_active": u.is_active, "version": u.version, "occurred_at": _now().isoformat()}))
