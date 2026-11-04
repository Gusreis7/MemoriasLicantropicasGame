"""Contratos privados da convivência. Nunca projetar SocialState para o jogador."""

from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import AwareDatetime, Field

from memorias_licantropicas.contracts.model import Contract, ConversationMessage


class ExchangeRecord(Contract):
    conversation_id: UUID
    npc_id: str
    day: int | None = Field(default=None, ge=1)
    incoming: ConversationMessage
    outgoing: ConversationMessage


class KnowledgeEntry(Contract):
    id: UUID
    owner_id: str
    root_id: UUID
    source_message_id: UUID
    speaker_id: str
    claimed_source_id: str | None = None
    source_span: str
    proposition: str
    subject_ids: tuple[str, ...] = ()
    parent_ids: tuple[UUID, ...] = ()
    kind: Literal['report', 'interpretation', 'denial', 'correction', 'literal'] = 'report'
    confidence: Literal['low', 'medium', 'high'] = 'low'
    stance: Literal['undecided', 'believes', 'doubts', 'rejects'] = 'undecided'
    day: int | None = Field(default=None, ge=1)
    origin: Literal['dialogue', 'authored'] = 'dialogue'
    visibility: Literal['public', 'trusted', 'private'] = 'public'
    disclosure_threshold: int = Field(default=0, ge=0, le=100)
    created_at: AwareDatetime


class Relationship(Contract):
    actor_id: str
    target_id: str
    sentiment_label: str = "indiferença"
    sentiments: dict[str, Annotated[int, Field(ge=0, le=100)]] = Field(default_factory=dict)
    affinity: int = Field(default=0, ge=-100, le=100)
    trust: int = Field(default=0, ge=-100, le=100)
    resentment: int = Field(default=0, ge=0, le=100)
    suspicion: int = Field(default=0, ge=0, le=100)
    loyalty: int = Field(default=0, ge=0, le=100)
    causes: tuple[UUID, ...] = ()


class SocialMessage(Contract):
    id: UUID
    sender_id: str
    content: str = Field(min_length=1, max_length=2400)
    created_at: AwareDatetime
    claim_ids: tuple[UUID, ...] = ()
    intent: Literal['warn', 'ask', 'confront', 'repeat', 'interpret', 'deny', 'correct', 'withhold', 'end', 'accuse', 'defend', 'confide'] = 'ask'


class Encounter(Contract):
    id: UUID
    day: int
    slot: int
    participant_ids: tuple[str, str]
    location_id: str
    phase: Literal['travelling', 'talking', 'finished', 'interrupted', 'failed', 'refused']
    started_at: AwareDatetime
    deadline: AwareDatetime
    arrival_at: AwareDatetime
    route: tuple[str, ...] = ()
    origin_location_id: str
    messages: tuple[SocialMessage, ...] = ()
    topic_ids: tuple[UUID, ...] = ()
    reason: str | None = None


class SocialDay(Contract):
    day: int
    slots: tuple[int, ...] = ()
    speech_calls: int = Field(default=0, ge=0, le=16)
    extraction_calls: int = Field(default=0, ge=0, le=8)


class SocialState(Contract):
    game_id: UUID
    version: Literal['1'] = '1'
    revision: int = Field(default=0, ge=0)
    exchange_cursor: int = Field(default=0, ge=0)
    seeded_topics_version: int = Field(default=0, ge=0)
    knowledge: tuple[KnowledgeEntry, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    encounters: tuple[Encounter, ...] = ()
    days: tuple[SocialDay, ...] = ()


class SocialRepository(Protocol):
    async def get(self, game_id: UUID) -> SocialState: ...

    async def save(self, state: SocialState, expected_revision: int, *,
                   world=None, expected_world_revision: int | None = None,
                   require_day: int | None = None, require_npcs: tuple[str, ...] = (),
                   require_player_idle: bool = False, events: tuple[dict, ...] = ()) -> bool: ...

    async def exchanges(self, game_id: UUID, offset: int, limit: int = 4) -> tuple[ExchangeRecord, ...]: ...

    async def recent_exchanges(self, game_id: UUID, limit: int = 100) -> tuple[ExchangeRecord, ...]: ...

    async def pending_npc_ids(self, game_id: UUID, cursor: int) -> tuple[str, ...]: ...

    async def backfill_history(self, game_id: UUID) -> bool: ...

    async def active_game_ids(self) -> tuple[UUID, ...]: ...

    def lease(self, game_id: UUID): ...


class KnowledgePolicy(Protocol):
    async def process_pending(self, game_id: UUID, day: int) -> bool: ...

    async def context(self, game_id: UUID, npc_id: str, other_id: str = 'player') -> dict: ...
