"""Contratos internos do ciclo: nunca serializar a investigação inteira em HTTP."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from src.contracts.model import Contract
from src.contracts.table import TableState
from src.modules.world.model import LocationID

Phase = Literal["day", "night", "finished"]
CaseStatus = Literal["active", "won", "lost"]
ItemKind = Literal["unique", "singular", "common"]


class ItemDefinition(Contract):
    id: str
    name: str
    kind: ItemKind
    description: str


class Evidence(Contract):
    examined: bool = False
    inspection_text: str | None = None
    crime_link_verified: bool = False
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
    cause: Literal["werewolf", "civil"] = "werewolf"
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
    dossier_fingerprint: str | None = None
    id: UUID
    day: int
    suspect_id: str
    evidence_ids: tuple[UUID, ...]
    testimony_ids: tuple[UUID, ...]
    report_ids: tuple[UUID, ...] = ()
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


class AssemblyMessage(Contract):
    speaker_id: str
    text: str


class AssemblySession(Contract):
    id: UUID
    suspect_id: str
    phase: Literal["debate", "resolved"] = "debate"
    evidence_ids: tuple[UUID, ...] = ()
    testimony_ids: tuple[UUID, ...] = ()
    messages: tuple[AssemblyMessage, ...] = ()
    opening_speech: str = ""
    reply: str = ""
    opened_at: AwareDatetime
    deadline: AwareDatetime
    remaining_day_seconds: float = Field(ge=0)
    relationships: tuple[dict, ...] = ()
    argument_strength: float = Field(default=0, ge=0, le=1)


class AssemblyVote(Contract):
    target_id: str | None = None
    voter_id: str
    expel: bool
    reason: str


class AssemblyRecord(Contract):
    opening_speech: str = ""
    reply: str = ""
    messages: tuple[AssemblyMessage, ...] = ()
    nominated_id: str | None = None
    evidence_ids: tuple[UUID, ...] = ()
    testimony_ids: tuple[UUID, ...] = ()
    suspect_id: str
    day: int
    votes: tuple[AssemblyVote, ...]
    required_votes: int
    expelled: bool
    outcome: Literal["werewolf", "innocent", "no_majority", "player_expelled"]
    created_at: AwareDatetime


class Achievement(Contract):
    id: str
    title: str
    description: str
    unlocked_at: AwareDatetime
    source_message_id: UUID | None = None
    source_npc_id: str | None = None


class MurderPlot(Contract):
    planner_id: str
    target_id: str
    status: Literal["planning", "succeeded", "frustrated", "interrupted"] = "planning"
    attempts: int = Field(default=0, ge=0)
    stress: int = Field(default=0, ge=0, le=100)


class NightStory(Contract):
    seed: str
    skipped_nights: int = Field(default=0, ge=0, le=1)
    plot: MurderPlot | None = None


class InvestigationState(Contract):
    table: TableState = Field(default_factory=TableState)
    night_story: NightStory | None = None
    active_evidence_by_npc: dict[str, UUID] = Field(default_factory=dict)
    achievements: tuple[Achievement, ...] = ()
    game_id: UUID
    revision: int = Field(default=0, ge=0)
    version: Literal["2"] = "2"
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
    dialogue_events: tuple[dict, ...] = ()
    assembly_session: AssemblySession | None = None
    assembly: AssemblyRecord | None = None
    expelled_npc_ids: tuple[str, ...] = ()
    ending_method: Literal["detention", "confession", "survival", "assembly", "player_expelled"] | None = None


class CaseEvent(Contract):
    type: str
    data: dict
    source: str = "rules"


class CaseTransition(Contract):
    state: InvestigationState
    events: tuple[CaseEvent, ...] = ()
