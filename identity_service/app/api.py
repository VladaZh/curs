import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .schemas import (
    AdminCreateUser,
    AdminPatchUser,
    LoginIn,
    MePatch,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserOut,
)
from .security import CurrentUser, decode_access_token
from .service import IdentityService

router = APIRouter(prefix="/v1")
bearer = HTTPBearer()


def get_service(session: AsyncSession = Depends(get_session)) -> IdentityService:
    return IdentityService(session)


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> CurrentUser:
    return decode_access_token(creds.credentials)


@router.post("/auth/register", response_model=UserOut, status_code=201)
async def register(body: RegisterIn, svc: IdentityService = Depends(get_service)):
    return await svc.register(body)


@router.post("/auth/login", response_model=TokenPair)
async def login(body: LoginIn, svc: IdentityService = Depends(get_service)):
    return await svc.login(body.email, body.password)


@router.post("/auth/refresh", response_model=TokenPair)
async def refresh(body: RefreshIn, svc: IdentityService = Depends(get_service)):
    return await svc.refresh(body.refresh_token)


@router.post("/auth/logout", status_code=204)
async def logout(body: RefreshIn, svc: IdentityService = Depends(get_service)):
    await svc.logout(body.refresh_token)
    return Response(status_code=204)


@router.get("/users/me", response_model=UserOut)
async def me(
    svc: IdentityService = Depends(get_service),
    actor: CurrentUser = Depends(current_user),
):
    return await svc.get_user(actor.id)


@router.patch("/users/me", response_model=UserOut)
async def update_me(
    body: MePatch,
    svc: IdentityService = Depends(get_service),
    actor: CurrentUser = Depends(current_user),
):
    return await svc.update_me(actor, body)


@router.post("/admin/users", response_model=UserOut, status_code=201)
async def admin_create(
    body: AdminCreateUser,
    svc: IdentityService = Depends(get_service),
    actor: CurrentUser = Depends(current_user),
):
    return await svc.admin_create_user(actor, body)


@router.patch("/admin/users/{user_id}", response_model=UserOut)
async def admin_update(
    user_id: uuid.UUID,
    body: AdminPatchUser,
    svc: IdentityService = Depends(get_service),
    actor: CurrentUser = Depends(current_user),
):
    return await svc.admin_update_user(actor, user_id, body)


@router.post("/admin/resync", status_code=202)
async def resync(
    svc: IdentityService = Depends(get_service),
    actor: CurrentUser = Depends(current_user),
):
    return {"events_queued": await svc.resync(actor)}
