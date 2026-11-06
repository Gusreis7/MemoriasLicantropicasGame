"""Projeções públicas: não incluem dono real, veracidade ou culpado antes do fim."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from src.contracts.investigation import CaseStatus, ItemKind, Phase
from src.contracts.model import Contract
from src.modules.world.model import LocationID


class SearchRequest(Contract):
    pass


class SkipDayRequest(Contract):
    day: int = Field(ge=1, strict=True)


class PresentRequest(Contract):
    npc_id: str = Field(min_length=1, max_length=40)


class AccuseRequest(Contract):
    suspect_id: str = Field(min_length=1, max_length=40)
    evidence_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    testimony_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    report_ids: tuple[UUID, ...] = Field(default=(), max_length=100)


class InterrogateRequest(Contract):
    npc_id: str = Field(min_length=1, max_length=40)
    day: int = Field(ge=0)
    period: Literal["night", "day"] = "night"


class ConfrontRequest(Contract):
    npc_id: str = Field(min_length=1, max_length=40)
    evidence_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    testimony_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    interrogation_ids: tuple[UUID, ...] = Field(default=(), max_length=100)


class JournalPublic(Contract):
    illustration: str = "crime_street"
    day: int
    title: str = "O Clarim do Rio"
    headline: str
    body: str
    victim_id: str | None
    victim_name: str | None
    suspicious_death_count: int = Field(default=0, ge=0)
    location_id: LocationID | None
    detention_outcome: Literal["none", "released", "transformed"]


class CrimePublic(Contract):
    id: UUID
    day: int
    victim_id: str
    victim_name: str
    location_id: LocationID
    x: float
    remaining_clues: int


class EvidencePublic(Contract):
    examined: bool = False
    inspection_text: str | None = None
    id: UUID
    crime_id: UUID
    item_id: str
    name: str
    kind: ItemKind
    description: str


class TestimonyPublic(Contract):
    id: UUID
    day: int
    evidence_id: UUID
    witness_id: str
    witness_name: str
    recognition: Literal["recognizes", "denies", "unknown"]
    claimed_owner_id: str | None
    text: str


class AccusationReviewPublic(Contract):
    ready: bool
    route: Literal["examined_trace", "corroborated_personal_marks", "witness_reports"] | None = None
    missing: tuple[str, ...] = ()
    reason: str


class AccusationPublic(Contract):
    id: UUID
    day: int
    suspect_id: str
    suspect_name: str
    evidence_ids: tuple[UUID, ...]
    testimony_ids: tuple[UUID, ...]
    report_ids: tuple[UUID, ...] = ()
    accepted: bool
    reason: str


class EndingPublic(Contract):
    result: Literal["won", "lost"]
    message: str
    werewolf_id: str
    method: Literal["detention", "confession", "survival", "assembly", "player_expelled"] = "detention"


class ActivityClaimPublic(Contract):
    npc_id: str
    location_id: LocationID
    companion_ids: tuple[str, ...]
    activity: str
    source: Literal["observed", "heard"]


class InterrogationPublic(Contract):
    id: UUID
    npc_id: str
    npc_name: str
    day: int
    period: Literal["day", "night"]
    location_id: LocationID | None
    companion_ids: tuple[str, ...]
    activity: str
    text: str
    observations: tuple[ActivityClaimPublic, ...]


class ConfrontationPublic(Contract):
    id: UUID
    npc_id: str
    day: int
    evidence_ids: tuple[UUID, ...]
    testimony_ids: tuple[UUID, ...]
    interrogation_ids: tuple[UUID, ...]
    confessed: bool
    text: str


class AchievementPublic(Contract):
    id: str
    title: str
    description: str
    unlocked_at: AwareDatetime
    source_message_id: UUID | None = None
    source_npc_id: str | None = None


class TableStatementPublic(Contract):
    """Uma declaração efetivamente entregue a Floriano, com estado canônico."""

    id: UUID
    npc_id: str
    npc_name: str
    subject_id: str | None = None
    day: int
    period: Literal["day", "night"] | None = None
    kind: Literal["alibi", "sighting", "suspicion", "gossip", "secret", "public_fact"]
    text: str
    location_id: LocationID | None = None
    companion_ids: tuple[str, ...] = ()
    alibi_status: Literal["alone", "accompanied", "partial", "unavailable"] | None = None
    confirmation_status: Literal["confirmed", "awaiting_confirmation", "alone", "partial", "unavailable", "reported"] = "reported"
    source_ids: tuple[UUID, ...] = ()
    admissible: bool = False


class CasePublic(Contract):
    achievements: tuple[AchievementPublic, ...] = ()
    achievement_total: int = 7
    game_id: UUID
    revision: int
    day: int
    phase: Phase
    status: CaseStatus
    server_time: AwareDatetime
    phase_ends_at: AwareDatetime
    seconds_remaining: int
    journal: tuple[JournalPublic, ...]
    crimes: tuple[CrimePublic, ...]
    inventory: tuple[EvidencePublic, ...]
    testimonies: tuple[TestimonyPublic, ...]
    accusations: tuple[AccusationPublic, ...]
    detained_npc_id: str | None
    ending: EndingPublic | None
    assembly_session: dict | None = None
    assembly: dict | None = None
    expelled_npc_ids: tuple[str, ...] = ()
    interrogations: tuple[InterrogationPublic, ...] = ()
    confrontations: tuple[ConfrontationPublic, ...] = ()
    case_reports: tuple[TableStatementPublic, ...] = ()


class AssemblyRequest(AccuseRequest):
    pass


class AssemblyOpenRequest(AssemblyRequest):
    speech: str = Field(default="", max_length=800)


class AssemblyResolveRequest(Contract):
    reply: str = Field(default="", max_length=500)
