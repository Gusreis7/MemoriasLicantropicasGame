import asyncio
from uuid import uuid4

import pytest

from src.contracts.errors import ConflictError, LLMUnavailableError
from src.infrastructure.conversation_gate import RedisConversationGate

pytestmark = pytest.mark.anyio


async def test_gate_is_shared_by_instances_and_released(storage):
    first = RedisConversationGate(storage.client, storage.prefix)
    second = RedisConversationGate(storage.client, storage.prefix)
    game, conversation = uuid4(), uuid4()
    async with first.hold(game, conversation):
        with pytest.raises(ConflictError):
            async with second.hold(game, conversation):
                pytest.fail("Reserva concorrente não pode entrar")
    async with second.hold(game, conversation):
        pass


async def test_gate_timeout_is_bounded_and_releases_reservation(storage):
    gate = RedisConversationGate(storage.client, storage.prefix, timeout_seconds=0.02)
    game, conversation = uuid4(), uuid4()
    with pytest.raises(LLMUnavailableError):
        async with gate.hold(game, conversation):
            await asyncio.sleep(1)
    async with gate.hold(game, conversation):
        pass


async def test_old_owner_does_not_remove_new_reservation(storage):
    gate = RedisConversationGate(storage.client, storage.prefix)
    game, conversation = uuid4(), uuid4()
    key = f"{storage.prefix}:game:{{{game}}}:conversation:{conversation}:busy"
    async with gate.hold(game, conversation):
        await storage.client.set(key, "new-owner", ex=10)
    assert await storage.client.get(key) == "new-owner"
