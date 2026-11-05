"""Reserva distribuída curta por conversa, sem manter transação durante inferência."""

import asyncio
from contextlib import asynccontextmanager
from math import ceil
from uuid import UUID, uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError, WatchError

from src.contracts.errors import ConflictError, LLMUnavailableError, StorageUnavailableError


class RedisConversationGate:
    def __init__(self, client: Redis, prefix: str = "ml:v1", timeout_seconds: float = 40):
        self._client = client
        self._prefix = prefix
        self._timeout = timeout_seconds

    @asynccontextmanager
    async def hold(self, game_id: UUID, conversation_id: UUID):
        key = f"{self._prefix}:game:{{{game_id}}}:conversation:{conversation_id}:busy"
        owner = uuid4().hex
        try:
            acquired = await self._client.set(key, owner, nx=True, ex=ceil(self._timeout + 10))
        except RedisError:
            raise StorageUnavailableError("Reserva de conversa indisponível.") from None
        if not acquired:
            raise ConflictError("A conversa já está processando uma mensagem.")
        try:
            async with asyncio.timeout(self._timeout):
                yield
        except TimeoutError:
            raise LLMUnavailableError("A conversa excedeu o tempo de resposta.", code="llm_timeout") from None
        finally:
            # Só o dono pode liberar a reserva; não remove eventual reserva posterior.
            try:
                for _ in range(3):
                    try:
                        async with self._client.pipeline() as pipe:
                            await pipe.watch(key)
                            if await pipe.get(key) != owner:
                                break
                            pipe.multi()
                            pipe.delete(key)
                            await pipe.execute()
                            break
                    except WatchError:
                        continue
            except RedisError:
                # A reserva tem TTL; não esconder o resultado/erro original da operação.
                pass
