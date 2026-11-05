"""Proposta externa do mestre separada da decisão e dos metadados internos."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from memorias_licantropicas.contracts.model import ConversationMessage


class AssessmentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    useful: bool = False
    useful_quote: str = Field(default="", max_length=2400)
    kind: Literal[
        "conversation",
        "alibi",
        "suspicion",
        "confidence",
        "partial_admission",
        "admission",
    ] = "conversation"
    quote: str = Field(default="", max_length=2400)
    confidence: float = Field(default=0, ge=0, le=1)
    own_assertion: bool = False
    surrender: bool = False
    period: Literal["day", "night"] | None = None
    day: int | None = Field(default=None, ge=0)
    issues: tuple[
        Literal[
            "invented_event",
            "unauthorized_confidence",
            "narrator_style",
            "wrong_address",
            "off_topic",
        ],
        ...,
    ] = Field(default=(), max_length=5)


class DialogueAssessment(AssessmentProposal):
    """Decisão interna; os campos de controle não são fornecidos pelo modelo."""

    repair_support_id: str | None = Field(default=None, max_length=120)
    corrected_reply: str | None = Field(default=None, max_length=900)
    discovery_ids: tuple[str, ...] = Field(default=(), max_length=7)
    eligible_discovery_ids: tuple[str, ...] = Field(default=(), max_length=7)
    source: Literal["local", "model", "fallback"] = "local"
    attempts: int = Field(default=0, ge=0, le=2)
    error_code: str | None = Field(default=None, max_length=80)


class PendingDialogueExchange(BaseModel):
    """Outbox versionado pelo schema, com autoria vinculada à sessão no servidor."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    game_id: UUID
    conversation_id: UUID
    npc_id: str = Field(min_length=1, max_length=80)
    incoming: ConversationMessage
    outgoing: ConversationMessage
    assessment: DialogueAssessment

    @model_validator(mode="after")
    def validate_authorship(self):
        if (
            self.outgoing.sender_id != self.npc_id
            or self.incoming.sender_id == self.npc_id
        ):
            raise ValueError("Outbox authorship mismatch")
        if self.incoming.id == self.outgoing.id:
            raise ValueError("Outbox messages must have distinct IDs")
        return self
