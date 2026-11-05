"""Implementação local do catálogo versionado, sem I/O externo."""

from src.contracts.model import CharacterProfile
from src.modules.characters.catalog import CHARACTERS, CONTENT_VERSION


class CatalogCharacterRepository:
    content_version = CONTENT_VERSION

    async def list(self) -> tuple[CharacterProfile, ...]:
        return CHARACTERS

    async def get(self, character_id: str) -> CharacterProfile | None:
        return next((profile for profile in CHARACTERS if profile.id == character_id), None)
