"""Transação Redis do ciclo, estado da partida, mundo e eventos."""

import json
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError, WatchError

from src.contracts.errors import ConflictError, StorageUnavailableError
from src.contracts.investigation import CaseEvent, InvestigationState
from src.contracts.model import GameState
from src.modules.world.model import WorldState


def _decode(value, model):
    try:
        return model.model_validate_json(value)
    except (ValueError, TypeError, ValidationError):
        raise StorageUnavailableError("Registro do ciclo persistido inválido.") from None


class RedisTurnRepository:
    def __init__(self, client: Redis, prefix: str = "ml:v1") -> None:
        if not prefix or "{" in prefix or "}" in prefix:
            raise ValueError("Prefixo Redis inválido.")
        self._client = client
        self._prefix = prefix

    def _base(self, game_id: UUID) -> str:
        return f"{self._prefix}:game:{{{game_id}}}"

    async def get(self, game_id: UUID) -> InvestigationState | None:
        try:
            value = await self._client.get(f"{self._base(game_id)}:investigation")
        except RedisError:
            raise StorageUnavailableError("Persistência do ciclo indisponível.") from None
        if value is None:
            return None
        state = _decode(value, InvestigationState)
        if state.game_id != game_id:
            raise StorageUnavailableError("Identidade do ciclo persistido inválida.")
        return state

    async def read_snapshot(
        self, game_id: UUID,
    ) -> tuple[GameState | None, WorldState | None, InvestigationState | None]:
        """Lê os três documentos no mesmo instante, sem reservar o jogador.

        GETs numa transação somente de leitura mantêm erros de tipo Redis. MGET
        devolveria nil também para uma chave com tipo incorreto, confundindo
        corrupção com ausência de agregado.
        """
        base = self._base(game_id)
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.get(f"{base}:state")
                pipe.get(f"{base}:world")
                pipe.get(f"{base}:investigation")
                raw_game, raw_world, raw_state = await pipe.execute()
        except RedisError:
            raise StorageUnavailableError("Persistência do ciclo indisponível.") from None
        game = _decode(raw_game, GameState) if raw_game is not None else None
        world = _decode(raw_world, WorldState) if raw_world is not None else None
        state = _decode(raw_state, InvestigationState) if raw_state is not None else None
        if ((game is not None and game.id != game_id)
                or (world is not None and world.game_id != game_id)
                or (state is not None and state.game_id != game_id)):
            raise StorageUnavailableError("Identidade do ciclo persistido inválida.")
        return game, world, state

    async def commit(
        self, *, previous: InvestigationState | None, state: InvestigationState,
        previous_game: GameState, game: GameState,
        previous_world: WorldState, world: WorldState,
        events: tuple[CaseEvent, ...], occurred_at: datetime,
    ) -> None:
        """Nenhuma alteração parcial: validar tipos de todas as chaves antes do MULTI."""
        if (state.game_id != game.id or world.game_id != game.id
                or previous_game.id != game.id or previous_world.game_id != game.id):
            raise ValueError("Identidade inconsistente na transição.")
        if ((previous is None and state.revision != 0)
                or (previous is not None and (previous.game_id != game.id
                                             or state.revision != previous.revision + 1))):
            raise ValueError("Revisão inválida na transição.")
        if (game.created_at != previous_game.created_at
                or game.content_version != previous_game.content_version
                or tuple((npc.character_id, npc.role) for npc in game.characters)
                != tuple((npc.character_id, npc.role) for npc in previous_game.characters)
                or any(not before.alive and after.alive
                       for before, after in zip(previous_game.characters, game.characters, strict=True))):
            raise ValueError("A transição não pode alterar o sorteio ou ressuscitar personagens.")
        base = self._base(game.id)
        case_key, game_key, world_key, events_key = (
            f"{base}:investigation", f"{base}:state", f"{base}:world", f"{base}:events",
        )
        encoded_events = [json.dumps({
            "id": str(uuid4()), "type": event.type, "source": event.source,
            "occurred_at": occurred_at.isoformat(), "data": event.data,
        }, ensure_ascii=False) for event in events]
        try:
            for _ in range(5):
                try:
                    async with self._client.pipeline() as pipe:
                        await pipe.watch(case_key, game_key, world_key, events_key, f"{base}:social")
                        current_case, current_game, current_world = await pipe.mget(case_key, game_key, world_key)
                        if current_game is None or current_world is None:
                            raise StorageUnavailableError("Estado do ciclo incompleto.")
                        stored_game = _decode(current_game, GameState)
                        stored_world = _decode(current_world, WorldState)
                        if (stored_game != previous_game or stored_world.game_id != world.game_id
                                or stored_world.revision != previous_world.revision):
                            raise ConflictError("A partida mudou durante a transição; consulte o estado atual.")
                        if previous is None:
                            if current_case is not None:
                                raise ConflictError("O ciclo já foi inicializado.")
                        elif current_case is None:
                            raise StorageUnavailableError("O ciclo desapareceu durante a transição.")
                        else:
                            stored_case = _decode(current_case, InvestigationState)
                            if stored_case.game_id != game.id:
                                raise StorageUnavailableError("Identidade do ciclo persistido inválida.")
                            if stored_case.revision != previous.revision:
                                raise ConflictError("O ciclo mudou; consulte o estado atual.")
                        # LLEN antes de MULTI detecta chave corrompida sem gravar os estados.
                        await pipe.llen(events_key)
                        social_update = None
                        if state.assembly and (previous is None or previous.assembly is None) and state.assembly.outcome == "innocent":
                            from src.contracts.social import SocialState
                            from src.modules.knowledge.rules import apply_relationship, initial_relationships
                            from uuid import uuid5, NAMESPACE_URL
                            raw_social = await pipe.get(f"{base}:social")
                            social_update = _decode(raw_social, SocialState) if raw_social else SocialState(game_id=game.id)
                            if social_update.game_id != game.id:
                                raise StorageUnavailableError("Identidade social inconsistente.")
                            ids = tuple(m.character_id for m in game.characters if m.alive)
                            if not social_update.relationships:
                                social_update = social_update.model_copy(update={"relationships": initial_relationships(ids)})
                            cause = uuid5(NAMESPACE_URL, f"{game.id}:assembly")
                            for actor in ids:
                                for target in (*ids, "player"):
                                    if actor != target:
                                        social_update = apply_relationship(social_update, actor, target, cause, resentment=5, trust=-3)
                            social_update = social_update.model_copy(update={"revision": social_update.revision + 1})
                        pipe.multi()
                        if social_update is not None:
                            pipe.set(f"{base}:social", social_update.model_dump_json())
                        pipe.set(case_key, state.model_dump_json())
                        pipe.set(f"{base}:table", state.table.model_dump_json())
                        pipe.set(game_key, game.model_dump_json())
                        pipe.set(world_key, world.model_dump_json())
                        if encoded_events:
                            pipe.rpush(events_key, *encoded_events)
                        await pipe.execute()
                        return
                except WatchError:
                    continue
        except RedisError:
            raise StorageUnavailableError("Persistência do ciclo indisponível.") from None
        raise ConflictError("O ciclo foi alterado concorrentemente; consulte o estado atual.")
