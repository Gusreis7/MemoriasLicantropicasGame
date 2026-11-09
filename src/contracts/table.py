"""Authoritative game-table records; persona prose never changes these fields."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from src.contracts.model import Contract
from src.modules.world.model import LocationID


class NightEncounter(Contract):
    id: UUID
    day: int
    location_id: LocationID
    participant_ids: tuple[str, ...]
    coverage: Literal["full", "partial"] = "full"


class NightPresence(Contract):
    id: UUID
    npc_id: str
    day: int
    location_id: LocationID | None
    encounter_id: UUID | None = None
    companion_ids: tuple[str, ...] = ()
    coverage: Literal["full", "partial", "unavailable"] = "full"


class TableObservation(Contract):
    id: UUID
    observer_id: str
    subject_id: str
    day: int
    location_id: LocationID
    kind: Literal["presence", "suspicious_presence"] = "presence"


class NightRecord(Contract):
    id: UUID
    day: int
    encounters: tuple[NightEncounter, ...] = ()
    presences: tuple[NightPresence, ...] = ()
    observations: tuple[TableObservation, ...] = ()
    created_at: AwareDatetime


class TableStatement(Contract):
    id: UUID
    kind: Literal["alibi", "sighting", "suspicion", "gossip", "secret", "public_fact"]
    speaker_id: str
    recipient_id: str = "player"
    subject_id: str | None = None
    day: int
    period: Literal["day", "night"] | None = None
    source_ids: tuple[UUID, ...] = ()
    root_id: UUID
    location_id: LocationID | None = None
    companion_ids: tuple[str, ...] = ()
    alibi_status: Literal["alone", "accompanied", "partial", "unavailable"] | None = None
    text: str
    created_at: AwareDatetime


class TableState(Contract):
    version: Literal["2"] = "2"
    nights: tuple[NightRecord, ...] = ()
    statements: tuple[TableStatement, ...] = ()


Index = Annotated[int, Field(strict=True, ge=0)]


class TableDeliveryPlan(BaseModel):
    """Compose a persona reply by selecting only the supplied equivalent phrases."""
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    opening: Index = Field(description='Index of an authorized opening.')
    variants: tuple[Index, ...] = Field(strict=False, min_length=1, max_length=16,
        description='One authorized variant index per fact, in the original order; omit nothing.')
    closing: Index = Field(description='Index of an authorized closing.')
