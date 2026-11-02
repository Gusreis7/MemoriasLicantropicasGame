"""Modelos internos v1. Nunca retornar estes objetos diretamente pela API."""

from typing import Literal
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
    id: UUID
    sender_id: str
    content: str = Field(min_length=1, max_length=8000)
    created_at: AwareDatetime


class ChatMessage(Contract):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMResponse(Contract):
    content: str = Field(min_length=1, max_length=8000)
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class HarnessReply(Contract):
    conversation_id: UUID
    message: ConversationMessage
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
