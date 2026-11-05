from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from src.modules.world.catalog import LOCATIONS
from src.modules.world.schema import LocationPublic, MoveRequest, TravelRequest, WorldSnapshot
from src.modules.world.service import WorldService

router = APIRouter(tags=["world"])


async def get_world_service(request: Request) -> WorldService:
    return request.app.state.services.world


Service = Annotated[WorldService, Depends(get_world_service)]


@router.get("/api/v1/world/locations", response_model=list[LocationPublic])
async def get_locations():
    return LOCATIONS


@router.get("/api/v1/games/{game_id}/world", response_model=WorldSnapshot)
async def get_world(game_id: UUID, service: Service):
    return await service.get(game_id)


@router.post("/api/v1/games/{game_id}/movement", response_model=WorldSnapshot)
async def move(game_id: UUID, body: MoveRequest, service: Service):
    return await service.move(game_id, body)


@router.post("/api/v1/games/{game_id}/travel", response_model=WorldSnapshot)
async def travel(game_id: UUID, body: TravelRequest, service: Service):
    return await service.travel(game_id, body)
