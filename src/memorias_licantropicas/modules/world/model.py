"""Estado privado do mundo. Não contém papéis ou objetivos dos personagens."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from memorias_licantropicas.contracts.model import Contract

LocationID = Literal["praca_verde", "cabana_capitu", "casa_verde", "cafe_largo", "cais_lanternas"]
Direction = Literal["left", "right", "idle"]


class WorldPlayer(Contract):
    location_id: LocationID = "praca_verde"
    # Limite legado para ler partidas anteriores; bounds atuais vêm do catálogo.
    x: float = Field(default=160, ge=32, le=1888)
    facing: Literal["left", "right"] = "right"
    movement_seq: int = Field(default=0, ge=0)
    direction: Direction = "idle"
    last_updated_at: AwareDatetime


class WorldNPC(Contract):
    npc_id: str
    location_id: LocationID
    x: float = Field(ge=32, le=1888)
    activity: Literal["idle", "travelling", "talking"] = "idle"
    social_encounter_id: UUID | None = None
    travel_destination_id: LocationID | None = None
    travel_arrives_at: AwareDatetime | None = None
    travel_started_at: AwareDatetime | None = None
    travel_origin_x: float | None = None
    travel_target_x: float | None = None
    travel_route: tuple[LocationID, ...] = ()
    social_partner_id: str | None = None


class WorldState(Contract):
    game_id: UUID
    world_version: Literal["1"] = "1"
    revision: int = Field(default=0, ge=0)
    player: WorldPlayer
    npcs: tuple[WorldNPC, ...]
