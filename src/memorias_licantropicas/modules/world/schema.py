"""Contratos públicos do mundo e comandos com revisão otimista."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from memorias_licantropicas.contracts.model import Contract
from memorias_licantropicas.modules.world.model import Direction, LocationID


class LocationExit(Contract):
    side: Literal["left", "right"]
    target_location_id: LocationID
    arrival_side: Literal["left", "right"]


class LocationPublic(Contract):
    id: LocationID
    name: str
    width: int = 960
    height: int = 360
    ground_y: int = 300
    background: str
    exits: tuple[LocationExit, ...] = ()


class MoveRequest(Contract):
    direction: Direction
    seq: int = Field(strict=True, ge=1)
    location_id: LocationID
    revision: int = Field(strict=True, ge=0)


class TravelRequest(Contract):
    target_location_id: LocationID
    revision: int = Field(strict=True, ge=0)
    exit_side: Literal["left", "right"] | None = None


class PlayerPublic(Contract):
    location_id: LocationID
    x: float
    facing: Literal["left", "right"]
    movement_seq: int


class VisibleNPC(Contract):
    npc_id: str
    name: str
    x: float
    sprite_id: str
    can_approach: bool
    activity: Literal["idle", "talking"] = "idle"
    social_partner_id: str | None = None


class WorldSnapshot(Contract):
    game_id: UUID
    world_version: Literal["1"]
    revision: int
    location: LocationPublic
    player: PlayerPublic
    visible_npcs: tuple[VisibleNPC, ...]
    travel_targets: tuple[LocationID, ...]
