"""Redis do mundo: insert-only no bootstrap e CAS a cada comando."""

import json
from uuid import UUID

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError, WatchError

from src.contracts.errors import ConflictError, StorageUnavailableError
from src.modules.world.model import WorldState


def _decode(value: str | bytes) -> WorldState:
    try:
        return WorldState.model_validate_json(value)
    except (ValidationError, ValueError, TypeError):
        raise StorageUnavailableError("Estado de mundo persistido inválido.") from None


class RedisWorldRepository:
    def __init__(self, client: Redis, prefix: str = "ml:v1") -> None:
        if not prefix or "{" in prefix or "}" in prefix:
            raise ValueError("Prefixo Redis inválido.")
        self._client = client
        self._prefix = prefix

    def _key(self, game_id: UUID) -> str:
        return f"{self._prefix}:game:{{{game_id}}}:world"

    async def create(self, world: WorldState) -> bool:
        """Ajuda fixtures/bootstrap explícito; não sobrescreve estado já existente."""
        try:
            return bool(await self._client.set(self._key(world.game_id), world.model_dump_json(), nx=True))
        except RedisError:
            raise StorageUnavailableError("Persistência do mundo indisponível.") from None

    async def get(self, game_id: UUID) -> WorldState | None:
        try:
            value = await self._client.get(self._key(game_id))
        except RedisError:
            raise StorageUnavailableError("Persistência do mundo indisponível.") from None
        if value is None:
            return None
        world = _decode(value)
        if world.game_id != game_id:
            raise StorageUnavailableError("Identidade de mundo persistida inválida.")
        return world

    async def save(self, world: WorldState, expected_revision: int, event: dict | None = None) -> bool:
        """Atualiza revisão e, se houver viagem, acrescenta seu evento na mesma transação."""
        if world.revision != expected_revision + 1:
            raise ValueError("A revisão do mundo deve avançar exatamente uma posição.")
        key = self._key(world.game_id)
        event_key = f"{self._prefix}:game:{{{world.game_id}}}:events"
        try:
            for _ in range(5):
                try:
                    async with self._client.pipeline() as pipe:
                        await pipe.watch(key, *([event_key] if event is not None else []))
                        value = await pipe.get(key)
                        if value is None:
                            return False
                        current = _decode(value)
                        if current.game_id != world.game_id:
                            raise StorageUnavailableError("Identidade de mundo persistida inválida.")
                        if current.revision != expected_revision:
                            return False
                        if event is not None:
                            # Redis MULTI não oferece rollback de um comando com tipo inválido.
                            await pipe.llen(event_key)
                        pipe.multi()
                        pipe.set(key, world.model_dump_json())
                        if event is not None:
                            pipe.rpush(event_key, json.dumps(event, ensure_ascii=False))
                        await pipe.execute()
                        return True
                except WatchError:
                    continue
        except RedisError:
            raise StorageUnavailableError("Persistência do mundo indisponível.") from None
        raise ConflictError("O mundo foi alterado concorrentemente; consulte o estado atual.")
