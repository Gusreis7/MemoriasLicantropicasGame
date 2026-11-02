"""Contratos internos do ciclo: nunca serializar a investigação inteira em HTTP."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from memorias_licantropicas.contracts.model import Contract
from memorias_licantropicas.modules.world.model import LocationID

Phase = Literal["day", "night", "finished"]
CaseStatus = Literal["active", "won", "lost"]
ItemKind = Literal["unique", "singular", "common"]


class ItemDefinition(Contract):
    id: str
    name: str
    kind: ItemKind
    description: str


class Evidence(Contract):
    id: UUID
    crime_id: UUID
    item_id: str
    description: str
    collected: bool = False
    deposited_by: str


class Crime(Contract):
    id: UUID
    day: int = Field(ge=0)
    victim_id: str
    location_id: LocationID
    x: float = 600
    occurred_at: AwareDatetime
    killer_id: str
    evidence: tuple[Evidence, ...]


class Testimony(Contract):
    id: UUID
    day: int
    evidence_id: UUID
    witness_id: str
    recognition: Literal["recognizes", "denies", "unknown"]
    claimed_owner_id: str | None = None
    text: str
    truthful: bool
    created_at: AwareDatetime


class Accusation(Contract):
    id: UUID
    day: int
    suspect_id: str
    evidence_ids: tuple[UUID, ...]
    testimony_ids: tuple[UUID, ...]
    accepted: bool
    reason: str
    created_at: AwareDatetime


class JournalEdition(Contract):
    illustration: str = "crime_street"
    day: int
    headline: str
    body: str
    victim_id: str | None = None
    suspicious_death_count: int = Field(default=0, ge=0)
    location_id: LocationID | None = None
    detention_outcome: Literal["none", "released", "transformed"] = "none"


class ActivityRecord(Contract):
    """Registro privado do motor; não confundir com versão declarada em interrogatório."""
    id: UUID
    npc_id: str
    day: int = Field(ge=0)
    period: Literal["day", "night"]
    location_id: LocationID
    companion_ids: tuple[str, ...] = ()
    activity: str
    observed_by: tuple[str, ...] = ()
    source: Literal["initial_scenario", "world_snapshot", "night_resolution"]
    occurred_at: AwareDatetime


class ActivityClaim(Contract):
    npc_id: str
    location_id: LocationID
    companion_ids: tuple[str, ...] = ()
    activity: str
    source: Literal["observed", "heard"] = "observed"


class Interrogation(Contract):
    id: UUID
    npc_id: str
    day: int = Field(ge=0)
    period: Literal["day", "night"]
    location_id: LocationID | None
    companion_ids: tuple[str, ...] = ()
    activity: str
    text: str
    observations: tuple[ActivityClaim, ...] = ()
    truthful: bool
    source_record_ids: tuple[UUID, ...] = ()
    created_at: AwareDatetime


class Confrontation(Contract):
    id: UUID
    npc_id: str
    day: int
    evidence_ids: tuple[UUID, ...] = ()
    testimony_ids: tuple[UUID, ...] = ()
    interrogation_ids: tuple[UUID, ...] = ()
    confessed: bool = False
    text: str
    # Pontuação e dificuldade são privados; nunca retorná-los no HTTP.
    pressure: int = 0
    created_at: AwareDatetime


class AssemblyVote(Contract):
    voter_id: str
    expel: bool
    reason: str


class AssemblyRecord(Contract):
    evidence_ids: tuple[UUID, ...] = ()
    testimony_ids: tuple[UUID, ...] = ()
    suspect_id: str
    day: int
    votes: tuple[AssemblyVote, ...]
    required_votes: int
    expelled: bool
    outcome: Literal["werewolf", "innocent", "no_majority"]
    created_at: AwareDatetime


class InvestigationState(Contract):
    game_id: UUID
    revision: int = Field(default=0, ge=0)
    version: Literal["1"] = "1"
    day: int = Field(default=1, ge=1)
    phase: Phase = "day"
    status: CaseStatus = "active"
    phase_ends_at: AwareDatetime
    crimes: tuple[Crime, ...] = ()
    testimonies: tuple[Testimony, ...] = ()
    accusations: tuple[Accusation, ...] = ()
    journal: tuple[JournalEdition, ...] = ()
    detained_npc_id: str | None = None
    activity_records: tuple[ActivityRecord, ...] = ()
    interrogations: tuple[Interrogation, ...] = ()
    confrontations: tuple[Confrontation, ...] = ()
    assembly: AssemblyRecord | None = None
    expelled_npc_ids: tuple[str, ...] = ()
    ending_method: Literal["detention", "confession", "survival", "assembly"] | None = None


class CaseEvent(Contract):
    type: str
    data: dict
    source: str = "rules"


class CaseTransition(Contract):
    state: InvestigationState
    events: tuple[CaseEvent, ...] = ()
