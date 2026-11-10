from datetime import UTC, datetime
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from src.contracts.errors import InteractionUnavailableError, AccessDeniedError, ConflictError, NotFoundError
from src.contracts.model import Conversation, ConversationMessage
from src.contracts.repository import (
    CharacterRepository, ConversationGate, GameRepository, MemoryRepository, InteractionPolicy, PlayerActionGate,
)
from src.modules.agents.service import HarnessService, PLAYER_ID
from src.modules.agents.guard import DialogueGuard, SAFE_DIALOGUE_REPLY
from src.modules.characters.catalog import supports_content_version
from src.modules.conversations.schema import (
    ConversationHistory, ConversationPublic, MessagePublic, MessageReply,
)


def public_message(message: ConversationMessage, private_markers: tuple[str, ...] = ()) -> MessagePublic:
    content = message.content
    if message.sender_id != PLAYER_ID:
        decision = DialogueGuard().inspect_output(content, () if message.narrative_authorized else private_markers,
            allow_role_disclosure=message.narrative_authorized)
        if not decision.allowed:
            content = decision.reply or SAFE_DIALOGUE_REPLY
    return MessagePublic(id=message.id, speaker="player" if message.sender_id == PLAYER_ID else "npc",
                         content=content, created_at=message.created_at,
                         useful=message.sender_id!=PLAYER_ID and message.narrative_authorized and message.useful and content==message.content)


class ConversationService:
    def __init__(self, characters: CharacterRepository, games: GameRepository,
                 memory: MemoryRepository, harness: HarnessService, gate: ConversationGate,
                 world: InteractionPolicy, player_gate: PlayerActionGate):
        self._characters = characters
        self._games = games
        self._memory = memory
        self._harness = harness
        self._gate = gate
        self._world = world
        self._player_gate = player_gate

    async def _validate_target(self, game_id: UUID, npc_id: str, allow_unavailable=False) -> None:
        game = await self._games.get(game_id)
        if game is None:
            raise NotFoundError("Partida não encontrada.")
        if not supports_content_version(game.content_version, self._characters.content_version):
            raise ConflictError("A partida usa uma versão anterior de personagens; crie uma nova partida.")
        target = next((npc for npc in game.characters if npc.character_id == npc_id), None)
        if target is None or await self._characters.get(npc_id) is None:
            raise NotFoundError("Persona não encontrada nesta partida.")
        if not target.alive and not allow_unavailable:
            raise InteractionUnavailableError("npc_unavailable")

    async def create(self, game_id: UUID, npc_id: str) -> ConversationPublic:
        async with self._player_gate.hold(game_id):
            return await self._create(game_id, npc_id)

    async def _create(self, game_id: UUID, npc_id: str) -> ConversationPublic:
        await self._validate_target(game_id, npc_id)
        await self._world.assert_can_talk(game_id, npc_id)
        existing = await self._memory.get_player_conversation(game_id, npc_id)
        if existing is not None:
            return await self.get(game_id, existing.id)
        conversation = Conversation(id=uuid4(), game_id=game_id, participant_ids=(PLAYER_ID, npc_id),
                                    created_at=datetime.now(UTC))
        if not await self._memory.create_conversation(conversation):
            raise ConflictError("Não foi possível criar a conversa.")
        return ConversationPublic(id=conversation.id, game_id=game_id, npc_id=npc_id,
                                  created_at=conversation.created_at)

    async def get(self, game_id: UUID, conversation_id: UUID, allow_unavailable=False) -> ConversationPublic:
        conversation = await self._memory.get_conversation(game_id, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversa não encontrada.")
        if PLAYER_ID not in conversation.participant_ids:
            raise AccessDeniedError("Conversa privada entre outros participantes.")
        npc_id = next(participant for participant in conversation.participant_ids if participant != PLAYER_ID)
        await self._validate_target(game_id, npc_id, allow_unavailable=allow_unavailable)
        return ConversationPublic(id=conversation.id, game_id=game_id, npc_id=npc_id,
                                  created_at=conversation.created_at)

    async def send(self, game_id: UUID, conversation_id: UUID, content: str) -> MessageReply:
        # O par é recuperado no servidor; cliente nunca escolhe remetente ou papel.
        async with self._gate.hold(game_id, conversation_id):
            conversation = await self.get(game_id, conversation_id)

            @asynccontextmanager
            async def action_scope():
                # Each graph node acquires and releases its own reservation.
                # No context manager crosses LangGraph task boundaries.
                async with self._player_gate.hold(game_id):
                    await self.get(game_id, conversation_id)
                    await self._world.assert_can_talk(game_id, conversation.npc_id)
                    yield

            reply = await self._harness.respond(game_id, conversation.npc_id, conversation_id,
                PLAYER_ID, content, action_scope=action_scope)
            return MessageReply(conversation_id=conversation_id, message=public_message(reply.message))

    async def history(self, game_id: UUID, conversation_id: UUID, limit: int = 50) -> ConversationHistory:
        conversation = await self.get(game_id, conversation_id, allow_unavailable=True)
        game = await self._games.get(game_id)
        profile = await self._characters.get(conversation.npc_id)
        if game is None or profile is None:
            raise NotFoundError("Persona não encontrada nesta partida.")
        npc = next(member for member in game.characters if member.character_id == conversation.npc_id)
        private_markers = HarnessService._private_markers(profile, npc)
        master = getattr(self._harness, '_session_master', None)
        if master is not None:
            async with self._player_gate.hold(game_id):
                await master.reconcile(game_id, conversation_id)
        messages = await self._memory.list_messages(game_id, conversation_id, PLAYER_ID, limit=limit)
        return ConversationHistory(conversation_id=conversation_id,
                                   messages=tuple(public_message(message, private_markers) for message in messages))

    async def close(self, game_id, conversation_id):
        async with self._player_gate.hold(game_id):
            conversation = await self.get(game_id, conversation_id, allow_unavailable=True)
            await self._world.release_dialogue(game_id, conversation.npc_id)
