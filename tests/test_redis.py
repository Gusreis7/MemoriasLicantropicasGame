import asyncio
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from memorias_licantropicas.contracts.errors import (
    AccessDeniedError, ConflictError, NotFoundError, StorageUnavailableError,
)
from memorias_licantropicas.infrastructure.redis_repository import RedisGameRepository

pytestmark = pytest.mark.anyio


async def test_insert_roundtrip_and_no_overwrite(storage, game):
    assert await storage.games.create(game) is True
    assert await storage.games.get(game.id) == game
    changed = game.model_copy(update={"content_version": "changed"})
    assert await storage.games.create(changed) is False
    assert await storage.games.get(game.id) == game
    assert await storage.games.get(uuid4()) is None


async def test_concurrent_inserts_only_one_wins(storage, game):
    results = await asyncio.gather(*(storage.games.create(game) for _ in range(5)))
    assert results.count(True) == 1
    assert await storage.games.get(game.id) == game


async def test_namespaces_are_isolated(storage, game):
    other = RedisGameRepository(storage.client, f"{storage.prefix}:other")
    await storage.games.create(game)
    assert await other.get(game.id) is None


async def test_data_survives_a_new_client(storage, game, request):
    await storage.games.create(game)
    url = request.config.getoption("--redis-url")
    if url:
        client = Redis.from_url(url, decode_responses=True)
    else:
        # Nova conexão ao mesmo servidor fakeredis, sem compartilhar o repository.
        import fakeredis
        client = fakeredis.FakeAsyncRedis(server=storage.server, decode_responses=True)
    try:
        assert await RedisGameRepository(client, storage.prefix).get(game.id) == game
    finally:
        await client.aclose()


async def test_corrupted_storage_fails_closed(storage, game):
    await storage.client.set(f"{storage.prefix}:game:{{{game.id}}}:state", "invalid-json")
    with pytest.raises(StorageUnavailableError):
        await storage.games.get(game.id)


async def test_connection_errors_are_translated(storage, game, monkeypatch):
    async def fail(*args, **kwargs):
        raise ConnectionError("private connection")
    monkeypatch.setattr(storage.client, "get", fail)
    with pytest.raises(StorageUnavailableError, match="Persistência indisponível"):
        await storage.games.get(game.id)


async def test_conversation_requires_existing_game_and_eligible_participants(storage, game, conversation):
    assert await storage.memory.create_conversation(conversation) is False
    absent = conversation.model_copy(update={"id": uuid4(), "game_id": uuid4()})
    with pytest.raises(NotFoundError):
        await storage.memory.create_conversation(absent)
    invalid = conversation.model_copy(update={"id": uuid4(), "participant_ids": ("player", "stranger")})
    with pytest.raises(AccessDeniedError):
        await storage.memory.create_conversation(invalid)
    assert await storage.memory.get_conversation(game.id, invalid.id) is None


async def test_append_roundtrip_deduplication_and_recent_history(storage, game, conversation, message_factory):
    messages = tuple(message_factory(f"fala {i}") for i in range(4))
    await storage.memory.append_messages(game.id, conversation.id, messages)
    await storage.memory.append_messages(game.id, conversation.id, messages)
    assert await storage.memory.list_messages(game.id, conversation.id, "player") == messages
    assert await storage.memory.list_messages(game.id, conversation.id, "bentinho", limit=2) == messages[-2:]


async def test_conflicting_id_rejects_entire_batch(storage, game, conversation, message_factory):
    original = message_factory()
    await storage.memory.append_messages(game.id, conversation.id, (original,))
    changed = original.model_copy(update={"content": "outra versão"})
    with pytest.raises(ConflictError):
        await storage.memory.append_messages(game.id, conversation.id, (message_factory(), changed))
    assert await storage.memory.list_messages(game.id, conversation.id, "player") == (original,)


async def test_duplicate_id_with_different_content_inside_batch_is_atomic(storage, game, conversation, message_factory):
    original = message_factory()
    with pytest.raises(ConflictError):
        await storage.memory.append_messages(game.id, conversation.id,
                                             (original, original.model_copy(update={"content": "changed"})))
    assert await storage.memory.list_messages(game.id, conversation.id, "player") == ()


async def test_conversation_privacy_and_cross_game_isolation(storage, game, conversation, message_factory):
    with pytest.raises(AccessDeniedError):
        await storage.memory.list_messages(game.id, conversation.id, "capitu")
    with pytest.raises(AccessDeniedError):
        await storage.memory.append_messages(game.id, conversation.id, (message_factory(sender_id="capitu"),))
    assert await storage.memory.get_conversation(uuid4(), conversation.id) is None
    with pytest.raises(NotFoundError):
        await storage.memory.list_messages(uuid4(), conversation.id, "player")
    assert await storage.memory.list_messages(game.id, conversation.id, "player") == ()


@pytest.mark.parametrize("limit", [0, -1, 201])
async def test_invalid_history_limits(storage, game, conversation, limit):
    with pytest.raises(ValueError):
        await storage.memory.list_messages(game.id, conversation.id, "player", limit=limit)
