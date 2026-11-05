from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, SecretStr


class AdminSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(AdminSchema):
    username: str
    password: SecretStr


class SessionPublic(AdminSchema):
    username: str


T = TypeVar("T")


class Page(AdminSchema, Generic[T]):
    items: list[T]
    total: int


class GameListItem(AdminSchema):
    id: UUID
    created_at: datetime
    status: str


class AdminCharacter(AdminSchema):
    character_id: str
    name: str
    grammatical_gender: Literal["masculine", "feminine"] | None = None
    role: str
    alive: bool
    location_id: str | None
    x: float | None


class KnownDeath(AdminSchema):
    victim_id: str
    victim_name: str
    killer_id: str | None
    killer_name: str | None
    attribution: str
    source: str


class AdminState(AdminSchema):
    game_id: UUID
    created_at: datetime
    content_version: str
    status: str
    werewolf_id: str
    characters: list[AdminCharacter]
    player: dict | None
    known_deaths: list[KnownDeath]
    world_version: str | None
    investigation: dict | None = None


class EventPublic(AdminSchema):
    id: str
    type: str
    occurred_at: str
    source: str
    data: dict


class AdminConversation(AdminSchema):
    id: UUID
    game_id: UUID
    participant_ids: tuple[str, str]
    created_at: datetime


class AdminMessage(AdminSchema):
    generation_status: Literal["accepted", "fallback", "guarded"] = "accepted"
    useful: bool = False
    id: UUID
    sender_id: str
    content: str
    created_at: datetime


class InteractionNode(AdminSchema):
    id: str
    name: str


class InteractionEdge(AdminSchema):
    source: str
    target: str
    message_count: int
    last_at: datetime | None
    conversation_id: UUID


class Interactions(AdminSchema):
    nodes: list[InteractionNode]
    edges: list[InteractionEdge]
