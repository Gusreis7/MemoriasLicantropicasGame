from typing import Annotated

from fastapi import APIRouter, Depends

from memorias_licantropicas.modules.characters.repository import CatalogCharacterRepository
from memorias_licantropicas.modules.characters.schema import CharacterPublic
from memorias_licantropicas.modules.characters.service import CharacterService

router = APIRouter(prefix="/api/v1/characters", tags=["characters"])


def get_character_service() -> CharacterService:
    return CharacterService(CatalogCharacterRepository())


@router.get("", response_model=list[CharacterPublic])
async def list_characters(
    service: Annotated[CharacterService, Depends(get_character_service)],
) -> tuple[CharacterPublic, ...]:
    return await service.list()


@router.get("/{character_id}", response_model=CharacterPublic)
async def get_character(
    character_id: str,
    service: Annotated[CharacterService, Depends(get_character_service)],
) -> CharacterPublic:
    return await service.get(character_id)
