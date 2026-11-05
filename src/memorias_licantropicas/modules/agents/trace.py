"""Traces técnicos de execução: nenhum prompt, fala ou papel secreto é registrado."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from memorias_licantropicas.infrastructure.events import event_json


class DialogueTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_id: UUID
    game_id: UUID
    conversation_id: UUID
    npc_id: str
    nodes: tuple[str, ...]
    attempts: int = Field(ge=0)
    review_attempts: int = Field(default=0, ge=0)
    status: Literal["completed", "fallback", "error", "cancelled"]
    error_code: str | None = None
    fallback: bool = False


TraceSink = Callable[[DialogueTrace], Awaitable[None]]


@dataclass
class DialogueAudit:
    """Objeto novo para cada ainvoke; nunca pertence ao singleton compilado."""

    invocation_id: UUID = field(default_factory=uuid4)
    nodes: list[str] = field(default_factory=list)
    attempts: int = 0
    review_attempts: int = 0
    status: str = "error"
    error_code: str | None = None
    fallback: bool = False


class RedisDialogueTraceRecorder:
    def __init__(self, client, prefix="ml:v1"):
        self._client, self._prefix = client, prefix

    async def record(self, trace: DialogueTrace) -> None:
        # Admin já lê o stream de eventos canônico; não há memória paralela do grafo.
        await self._client.rpush(
            f"{self._prefix}:game:{{{trace.game_id}}}:events",
            event_json("llm.dialogue.graph", trace.model_dump(mode="json"), "harness"),
        )
