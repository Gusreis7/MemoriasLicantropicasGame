from src.contracts.errors import NotFoundError
from src.contracts.model import CharacterProfile
from src.contracts.repository import CharacterRepository
from src.modules.characters.catalog import PUBLIC_BIOS
from src.modules.characters.schema import CharacterPublic


def public_character(profile: CharacterProfile) -> CharacterPublic:
    return CharacterPublic(
        id=profile.id,
        name=profile.name,
        bio=PUBLIC_BIOS.get(profile.id, ""),
        grammatical_gender=profile.grammatical_gender,
    )


class CharacterService:
    def __init__(self, repository: CharacterRepository) -> None:
        self._repository = repository

    async def list(self) -> tuple[CharacterPublic, ...]:
        return tuple(public_character(profile) for profile in await self._repository.list())

    async def get(self, character_id: str) -> CharacterPublic:
        profile = await self._repository.get(character_id)
        if profile is None:
            raise NotFoundError("Personagem não encontrado.")
        return public_character(profile)
