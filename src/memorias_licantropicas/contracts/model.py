"""Modelos internos v1. Nunca retornar estes objetos diretamente pela API."""

from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DialogueStrategy(Contract):
    voice: str
    priorities: tuple[str, ...]
    cooperate_when: str
    withhold_when: str
    pressure_response: str
    civil_tactic: str
    werewolf_tactic: str


class CharacterProfile(Contract):
    id: str
    name: str
    grammatical_gender: Literal["masculine", "feminine"] = "masculine"
    bio: str
    personality: str
    civil_objective: str
    werewolf_objective: str
    protected_secrets: tuple[str, ...] = ()
    role_awareness: Literal["aware", "denial"] = "aware"
    dialogue_strategy: DialogueStrategy | None = None


class GameCharacter(Contract):
    character_id: str
    role: Literal["civil", "werewolf"]
    alive: bool = True


class GameState(Contract):
    id: UUID
    created_at: AwareDatetime
    characters: tuple[GameCharacter, ...]
    content_version: str = "1"
    status: Literal["active", "won", "lost"] = "active"

    @model_validator(mode="after")
    def validate_cast(self) -> "GameState":
        ids = [character.character_id for character in self.characters]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("O elenco deve conter personagens únicos.")
        if sum(character.role == "werewolf" for character in self.characters) != 1:
            raise ValueError("A partida deve ter exatamente um lobisomem.")
        return self


class Conversation(Contract):
    id: UUID
    game_id: UUID
    participant_ids: tuple[str, str]
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_participants(self) -> "Conversation":
        if self.participant_ids[0] == self.participant_ids[1]:
            raise ValueError("A conversa precisa de dois participantes distintos.")
        return self


class ConversationMessage(Contract):
    generation_status: Literal["accepted", "fallback", "guarded"] = "accepted"
    useful: bool = False
    narrative_authorized: bool = False
    id: UUID
    sender_id: str
    content: str = Field(min_length=1, max_length=8000)
    created_at: AwareDatetime


class ChatMessage(Contract):
    role: Literal["system", "user", "assistant"]
    content: str


class NativeToolCall(Contract):
    """Chamada DTO recebida pelo protocolo; nunca executada como ação."""
    name: str = Field(min_length=1, max_length=80)
    args: dict[str, Any] = Field(repr=False)
    id: str | None = None
    type: Literal["tool_call"] = "tool_call"


class InvalidNativeToolCall(Contract):
    """Falha de argumentos recebidos; dados brutos não aparecem em repr/logs."""
    name: str | None = None
    args: str | None = Field(default=None, repr=False)
    id: str | None = None
    error: str | None = Field(default="invalid_tool_arguments", repr=False)
    type: Literal["invalid_tool_call"] = "invalid_tool_call"


class LLMResponse(Contract):
    content: str = Field(default="", max_length=8000, repr=False)
    tool_calls: tuple[NativeToolCall, ...] = Field(default=(), repr=False)
    invalid_tool_calls: tuple[InvalidNativeToolCall, ...] = Field(default=(), repr=False)
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class HarnessReply(Contract):
    conversation_id: UUID
    message: ConversationMessage
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
