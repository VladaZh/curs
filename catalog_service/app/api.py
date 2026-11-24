import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import CurrentUser, current_user
from .db import get_session
from .schemas import (
    HoursReplace,
    RestaurantCreate,
    RestaurantOut,
    RestaurantPatch,
    TableCreate,
    TableOut,
    TablePatch,
)
from .service import CatalogService

router = APIRouter(prefix="/v1")
router_api = APIRouter(prefix="/api")


def get_service(
    request: Request, session: AsyncSession = Depends(get_session)
) -> CatalogService:
    return CatalogService(session, request.app.state.cache)


@router_api.get("/version")
async def version():
    return 1


@router.get("/restaurants", response_model=list[RestaurantOut])
async def list_restaurants(
    city: str | None = None, svc: CatalogService = Depends(get_service)
):
    return await svc.list_restaurants(city)


@router.get("/restaurants/{restaurant_id}", response_model=RestaurantOut)
async def get_restaurant(
    restaurant_id: uuid.UUID, svc: CatalogService = Depends(get_service)
):
    return await svc.get_restaurant(restaurant_id)


@router.get("/restaurants/{restaurant_id}/tables", response_model=list[TableOut])
async def list_tables(
    restaurant_id: uuid.UUID, svc: CatalogService = Depends(get_service)
):
    return await svc.list_tables(restaurant_id)


@router.post("/restaurants", response_model=RestaurantOut, status_code=201)
async def create_restaurant(
    body: RestaurantCreate,
    svc: CatalogService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return await svc.create_restaurant(user, body)


@router.patch("/restaurants/{restaurant_id}", response_model=RestaurantOut)
async def update_restaurant(
    restaurant_id: uuid.UUID,
    body: RestaurantPatch,
    svc: CatalogService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return await svc.update_restaurant(user, restaurant_id, body)


@router.put("/restaurants/{restaurant_id}/hours", response_model=RestaurantOut)
async def replace_hours(
    restaurant_id: uuid.UUID,
    body: HoursReplace,
    svc: CatalogService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return await svc.replace_hours(user, restaurant_id, body.hours)


@router.post(
    "/restaurants/{restaurant_id}/tables", response_model=TableOut, status_code=201
)
async def add_table(
    restaurant_id: uuid.UUID,
    body: TableCreate,
    svc: CatalogService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return await svc.add_table(user, restaurant_id, body)


@router.patch("/restaurants/{restaurant_id}/tables/{table_id}", response_model=TableOut)
async def update_table(
    restaurant_id: uuid.UUID,
    table_id: uuid.UUID,
    body: TablePatch,
    svc: CatalogService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return await svc.update_table(user, restaurant_id, table_id, body)


@router.post("/admin/resync", status_code=202)
async def resync(
    svc: CatalogService = Depends(get_service),
    user: CurrentUser = Depends(current_user),
):
    return {"events_queued": await svc.resync(user)}
