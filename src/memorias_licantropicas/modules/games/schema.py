from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from memorias_licantropicas.modules.characters.schema import CharacterPublic


class CreateGameRequest(BaseModel):
    """O cliente não escolhe elenco, seed ou identidade do lobisomem."""

    model_config = ConfigDict(extra="forbid")


class GameCharacterPublic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    character: CharacterPublic
    alive: bool


class GamePublic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    created_at: datetime
    content_version: str
    status: Literal["active", "won", "lost"]
    characters: tuple[GameCharacterPublic, ...]
