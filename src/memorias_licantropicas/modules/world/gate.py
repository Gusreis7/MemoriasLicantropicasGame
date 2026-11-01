"""Reserva por partida/jogador compartilhada por movimento, viagem e diálogo."""

import asyncio
from contextlib import asynccontextmanager
from math import ceil
from uuid import UUID, uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError, WatchError

from memorias_licantropicas.contracts.errors import ConflictError, LLMUnavailableError, StorageUnavailableError


class RedisPlayerGate:
    def __init__(self, client: Redis, prefix: str = "ml:v1", timeout_seconds: float = 40):
        if timeout_seconds <= 0:
            raise ValueError("Tempo de reserva deve ser positivo.")
        self._client = client
        self._prefix = prefix
        self._timeout = timeout_seconds

    @asynccontextmanager
    async def hold(self, game_id: UUID):
        key = f"{self._prefix}:game:{{{game_id}}}:player:busy"
        owner = uuid4().hex
        try:
            acquired = await self._client.set(key, owner, nx=True, ex=ceil(self._timeout + 10))
        except RedisError:
            raise StorageUnavailableError("Reserva do jogador indisponível.") from None
        if not acquired:
            raise ConflictError("O jogador já está realizando uma ação.")
        try:
            async with asyncio.timeout(self._timeout):
                yield
        except TimeoutError:
            raise LLMUnavailableError("A ação do jogador excedeu o tempo de resposta.") from None
        finally:
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
                # Não esconder o resultado original; o TTL libera a reserva abandonada.
                pass
