"""Projeções públicas: não incluem dono real, veracidade ou culpado antes do fim."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from memorias_licantropicas.contracts.investigation import CaseStatus, ItemKind, Phase
from memorias_licantropicas.contracts.model import Contract
from memorias_licantropicas.modules.world.model import LocationID


class SearchRequest(Contract):
    pass


class PresentRequest(Contract):
    npc_id: str = Field(min_length=1, max_length=40)


class AccuseRequest(Contract):
    suspect_id: str = Field(min_length=1, max_length=40)
    evidence_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    testimony_ids: tuple[UUID, ...] = Field(default=(), max_length=100)


class JournalPublic(Contract):
    day: int
    title: str = "O Clarim do Rio"
    headline: str
    body: str
    victim_id: str | None
    victim_name: str | None
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


class AccusationPublic(Contract):
    id: UUID
    day: int
    suspect_id: str
    suspect_name: str
    evidence_ids: tuple[UUID, ...]
    testimony_ids: tuple[UUID, ...]
    accepted: bool
    reason: str


class EndingPublic(Contract):
    result: Literal["won", "lost"]
    message: str
    werewolf_id: str


class CasePublic(Contract):
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
