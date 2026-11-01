from datetime import UTC, datetime
from uuid import UUID, uuid4

from memorias_licantropicas.contracts.errors import AccessDeniedError, ConflictError, NotFoundError
from memorias_licantropicas.contracts.model import Conversation, ConversationMessage
from memorias_licantropicas.contracts.repository import (
    CharacterRepository, ConversationGate, GameRepository, MemoryRepository,
)
from memorias_licantropicas.modules.agents.service import HarnessService, PLAYER_ID
from memorias_licantropicas.modules.conversations.schema import (
    ConversationHistory, ConversationPublic, MessagePublic, MessageReply,
)


def public_message(message: ConversationMessage) -> MessagePublic:
    return MessagePublic(id=message.id, speaker="player" if message.sender_id == PLAYER_ID else "npc",
                         content=message.content, created_at=message.created_at)


class ConversationService:
    def __init__(self, characters: CharacterRepository, games: GameRepository,
                 memory: MemoryRepository, harness: HarnessService, gate: ConversationGate):
        self._characters = characters
        self._games = games
        self._memory = memory
        self._harness = harness
        self._gate = gate

    async def _validate_target(self, game_id: UUID, npc_id: str) -> None:
        game = await self._games.get(game_id)
        if game is None:
            raise NotFoundError("Partida não encontrada.")
        if game.content_version != self._characters.content_version:
            raise ConflictError("A partida usa uma versão anterior de personagens; crie uma nova partida.")
        target = next((npc for npc in game.characters if npc.character_id == npc_id), None)
        if target is None or await self._characters.get(npc_id) is None:
            raise NotFoundError("Persona não encontrada nesta partida.")
        if not target.alive:
            raise AccessDeniedError("Esta persona não pode conversar.")

    async def create(self, game_id: UUID, npc_id: str) -> ConversationPublic:
        await self._validate_target(game_id, npc_id)
        conversation = Conversation(id=uuid4(), game_id=game_id, participant_ids=(PLAYER_ID, npc_id),
                                    created_at=datetime.now(UTC))
        if not await self._memory.create_conversation(conversation):
            raise ConflictError("Não foi possível criar a conversa.")
        return ConversationPublic(id=conversation.id, game_id=game_id, npc_id=npc_id,
                                  created_at=conversation.created_at)

    async def get(self, game_id: UUID, conversation_id: UUID) -> ConversationPublic:
        conversation = await self._memory.get_conversation(game_id, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversa não encontrada.")
        if PLAYER_ID not in conversation.participant_ids:
            raise AccessDeniedError("Conversa privada entre outros participantes.")
        npc_id = next(participant for participant in conversation.participant_ids if participant != PLAYER_ID)
        await self._validate_target(game_id, npc_id)
        return ConversationPublic(id=conversation.id, game_id=game_id, npc_id=npc_id,
                                  created_at=conversation.created_at)

    async def send(self, game_id: UUID, conversation_id: UUID, content: str) -> MessageReply:
        # O par é recuperado no servidor; cliente nunca escolhe remetente ou papel.
        async with self._gate.hold(game_id, conversation_id):
            conversation = await self.get(game_id, conversation_id)
            reply = await self._harness.respond(game_id, conversation.npc_id, conversation_id, PLAYER_ID, content)
            return MessageReply(conversation_id=conversation_id, message=public_message(reply.message))

    async def history(self, game_id: UUID, conversation_id: UUID, limit: int = 50) -> ConversationHistory:
        await self.get(game_id, conversation_id)
        messages = await self._memory.list_messages(game_id, conversation_id, PLAYER_ID, limit=limit)
        return ConversationHistory(conversation_id=conversation_id,
                                   messages=tuple(public_message(message) for message in messages))
