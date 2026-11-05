"""Saídas propostas pelos agentes; nenhuma possui autoridade para alterar o mundo."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    message_id: UUID
    source_span: str = Field(min_length=8, max_length=1200)
    proposition: str = Field(min_length=8, max_length=1200)
    subject_ids: tuple[str, ...] = ()
    claimed_source_id: str | None = None
    kind: Literal["report", "interpretation", "denial", "correction"] = "report"
    parent_claim_ids: tuple[UUID, ...] = Field(default=(), max_length=2)
    disposition: Literal[
        "neutral", "accusation", "warning", "cooperation", "insult", "confidence_breach"
    ] = "neutral"


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    claims: tuple[ExtractedClaim, ...] = Field(max_length=8)


class SpeechProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    fala: str = Field(min_length=1, max_length=2400)
    intent: Literal[
        "warn",
        "ask",
        "confront",
        "repeat",
        "interpret",
        "deny",
        "correct",
        "withhold",
        "end",
        "accuse",
        "defend",
        "confide",
    ]
    claim_ids: tuple[UUID, ...] = Field(default=(), max_length=2)


class AssemblySpeech(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    speaker_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=180)


class AssemblyProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    messages: tuple[AssemblySpeech, ...] = Field(min_length=1, max_length=7)
    argument_strength: float = Field(ge=0, le=1)


class EditorialProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    opinion: str = Field(min_length=100, max_length=1800)
