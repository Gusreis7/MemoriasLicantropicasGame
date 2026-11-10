"""Falhas externas são tipadas; pareceres não escolhem metadados internos."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.contracts.errors import StorageUnavailableError
from src.contracts.model import ConversationMessage
from src.modules.session_master.service import SessionMasterService

pytestmark = pytest.mark.anyio


def exchange():
    return (
        ConversationMessage(
            id=uuid4(),
            sender_id="player",
            content="O que sabe sobre Capitu?",
            created_at=datetime.now(UTC),
        ),
        ConversationMessage(
            id=uuid4(),
            sender_id="escobar",
            content="Capitu e Bentinho vivem juntos; o ciúme dele é conhecido.",
            created_at=datetime.now(UTC),
        ),
    )


class Turns:
    async def require_day_locked(self, game_id):
        return SimpleNamespace(day=1)


async def test_corrupt_session_outbox_is_preserved_for_recovery_without_exposing_content(
    storage,
):
    master = SessionMasterService(
        Turns(), None, None, redis=storage.client, prefix=storage.prefix
    )
    game_id, conversation_id = uuid4(), uuid4()
    key = master._key(game_id, conversation_id)
    await storage.client.set(key, '{"SECRET_BAD_RECORD": true}')
    with pytest.raises(StorageUnavailableError) as failure:
        await master.reconcile(game_id, conversation_id)
    assert "SECRET_BAD_RECORD" not in str(failure.value)
    assert await storage.client.exists(key)


async def test_unused_extraction_provider_cannot_block_canonical_cursor(
    storage, catalog, game
):
    from src.contracts.social import ExchangeRecord
    from src.infrastructure.social_repository import (
        RedisSocialRepository,
    )
    from src.modules.knowledge.service import KnowledgeService
    from src.contracts.model import Conversation

    await storage.games.create(game)
    incoming, outgoing = exchange()
    conversation = Conversation(
        id=uuid4(),
        game_id=game.id,
        participant_ids=("player", "escobar"),
        created_at=game.created_at,
    )
    await storage.memory.create_conversation(conversation)
    record = ExchangeRecord(
        conversation_id=conversation.id,
        npc_id="escobar",
        incoming=incoming,
        outgoing=outgoing,
    )
    await storage.client.rpush(
        f"{storage.prefix}:game:{{{game.id}}}:social:exchanges",
        record.model_dump_json(),
    )
    repository = RedisSocialRepository(
        storage.client, storage.prefix, clock=lambda: game.created_at
    )

    class BrokenClient:
        async def complete(self, messages, *, tools=(), tool_choice=None):
            raise TypeError("fixture internal bug")

    assert await KnowledgeService(repository, catalog, BrokenClient()).process_pending(game.id, 1)
    state = await repository.get(game.id)
    assert state.exchange_cursor == 1
    # Extraction cannot invent facts or block the durable cursor any longer.
    assert any(entry.source_message_id == incoming.id and incoming.content in entry.proposition
               for entry in state.knowledge)
