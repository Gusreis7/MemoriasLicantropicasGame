"""Portas assíncronas de persistência. Sem imports de Redis ou FastAPI."""

from typing import Protocol
from uuid import UUID

from memorias_licantropicas.contracts.model import (
    CharacterProfile,
    Conversation,
    ConversationMessage,
    GameState,
)


class CharacterRepository(Protocol):
    async def list(self) -> tuple[CharacterProfile, ...]: ...

    async def get(self, character_id: str) -> CharacterProfile | None: ...


class GameRepository(Protocol):
    async def create(self, game: GameState) -> bool:
        """Insert-only; False se o ID já existir. Nunca sobrescrever sorteio."""
        ...

    async def get(self, game_id: UUID) -> GameState | None: ...


class MemoryRepository(Protocol):
    async def create_conversation(self, conversation: Conversation) -> bool: ...

    async def get_conversation(self, game_id: UUID, conversation_id: UUID) -> Conversation | None: ...

    async def append_messages(
        self, game_id: UUID, conversation_id: UUID,
        messages: tuple[ConversationMessage, ...],
    ) -> None:
        """Append atômico, participantes validados, deduplicação por ID de mensagem.

        Mesmo ID com conteúdo diferente é conflito. Não altera registros existentes.
        """
        ...

    async def list_messages(
        self, game_id: UUID, conversation_id: UUID, viewer_id: str, limit: int = 20,
    ) -> tuple[ConversationMessage, ...]:
        """Últimas mensagens em ordem cronológica; somente participantes podem ler."""
        ...
