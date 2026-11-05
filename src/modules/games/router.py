from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.modules.games.schema import CreateGameRequest, GamePublic
from src.modules.games.service import GameService

router = APIRouter(prefix="/api/v1/games", tags=["games"])


def get_game_service() -> GameService:
    raise RuntimeError("GameService deve ser configurado pela composição da aplicação.")


@router.post("", response_model=GamePublic, status_code=status.HTTP_201_CREATED)
async def create_game(
    service: Annotated[GameService, Depends(get_game_service)],
    request: CreateGameRequest | None = None,
) -> GamePublic:
    return await service.create()


@router.get("/{game_id}", response_model=GamePublic)
async def get_game(
    game_id: UUID,
    service: Annotated[GameService, Depends(get_game_service)],
) -> GamePublic:
    return await service.get(game_id)
