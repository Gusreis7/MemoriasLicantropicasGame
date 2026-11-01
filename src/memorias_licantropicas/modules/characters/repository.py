"""Implementação local do catálogo versionado, sem I/O externo."""

from memorias_licantropicas.contracts.model import CharacterProfile
from memorias_licantropicas.modules.characters.catalog import CHARACTERS


class CatalogCharacterRepository:
    async def list(self) -> tuple[CharacterProfile, ...]:
        return CHARACTERS

    async def get(self, character_id: str) -> CharacterProfile | None:
        return next((profile for profile in CHARACTERS if profile.id == character_id), None)
