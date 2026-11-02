"""Agregado social privado, CAS e reserva com fencing por token."""

import asyncio
import json
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import ValidationError
from redis.exceptions import RedisError, WatchError

from memorias_licantropicas.contracts.errors import StorageUnavailableError
from memorias_licantropicas.contracts.investigation import InvestigationState
from memorias_licantropicas.contracts.model import Conversation, ConversationMessage, GameState
from memorias_licantropicas.contracts.social import ExchangeRecord, SocialState
from memorias_licantropicas.modules.world.model import WorldState


class RedisSocialRepository:
    def __init__(self, client, prefix="ml:v1", clock=None, lease_seconds=45):
        if not prefix or "{" in prefix or "}" in prefix or lease_seconds <= 0:
            raise ValueError("Configuração da memória social inválida.")
        self._client, self._prefix = client, prefix
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lease_seconds = lease_seconds
        self._owner = ContextVar(f"social_owner_{id(self)}", default=None)

    def _base(self, game_id):
        return f"{self._prefix}:game:{{{game_id}}}"

    @staticmethod
    def _decode(raw, model, game_id):
        value = model.model_validate_json(raw)
        if value.game_id != game_id:
            raise ValueError("Identidade divergente.")
        return value

    async def get(self, game_id):
        try:
            raw = await self._client.get(f"{self._base(game_id)}:social")
            return self._decode(raw, SocialState, game_id) if raw is not None else SocialState(game_id=game_id)
        except (RedisError, ValidationError, ValueError, TypeError):
            raise StorageUnavailableError("Memória social indisponível.") from None

    async def _read_exchanges(self, raw_records, game_id, *, reader=None, game=None):
        if not raw_records:
            return ()
        reader = reader if reader is not None else self._client
        if game is None:
            raw_game = await reader.get(f"{self._base(game_id)}:state")
            game = GameState.model_validate_json(raw_game) if raw_game is not None else None
        if game is None or game.id != game_id:
            raise ValueError("Caso da conversa divergente.")
        cast = {member.character_id for member in game.characters}
        conversations = {}
        records = []
        for raw in raw_records:
            record = ExchangeRecord.model_validate_json(raw)
            if (record.npc_id not in cast or record.incoming.sender_id != "player"
                    or record.outgoing.sender_id != record.npc_id or record.incoming.id == record.outgoing.id):
                raise ValueError("Participantes da extração divergentes.")
            if record.conversation_id not in conversations:
                key = f"{self._base(game_id)}:conversation:{record.conversation_id}"
                # save usa o mesmo pipeline; metadados da conversa também ficam no snapshot CAS.
                if reader is not self._client:
                    await reader.watch(key)
                raw_conversation = await reader.get(key)
                conversation = Conversation.model_validate_json(raw_conversation) if raw_conversation is not None else None
                if (conversation is None or conversation.id != record.conversation_id
                        or conversation.game_id != game_id):
                    raise ValueError("Conversa da extração divergente.")
                conversations[record.conversation_id] = conversation
            conversation = conversations[record.conversation_id]
            if set(conversation.participant_ids) != {"player", record.npc_id}:
                raise ValueError("Par da extração divergente.")
            records.append(record)
        return tuple(records)

    async def exchanges(self, game_id, offset, limit=4):
        if offset < 0 or not 1 <= limit <= 4:
            raise ValueError("Janela de extração inválida.")
        try:
            raw = await self._client.lrange(f"{self._base(game_id)}:social:exchanges", offset, offset + limit - 1)
            return await self._read_exchanges(raw, game_id)
        except (RedisError, ValidationError, ValueError, TypeError):
            raise StorageUnavailableError("Fila de relatos indisponível.") from None

    async def recent_exchanges(self, game_id, limit=100):
        if not 1 <= limit <= 200:
            raise ValueError("Janela de relatos inválida.")
        try:
            raw = await self._client.lrange(f"{self._base(game_id)}:social:exchanges", -limit, -1)
            return await self._read_exchanges(raw, game_id)
        except (RedisError, ValidationError, ValueError, TypeError):
            raise StorageUnavailableError("Fila de relatos indisponível.") from None

    async def pending_npc_ids(self, game_id, cursor):
        if cursor < 0:
            raise ValueError("Cursor de extração inválido.")
        try:
            raw = await self._client.lrange(f"{self._base(game_id)}:social:exchanges", cursor, -1)
            records = await self._read_exchanges(raw, game_id)
            return tuple(dict.fromkeys(record.npc_id for record in records))
        except (RedisError, ValidationError, ValueError, TypeError):
            raise StorageUnavailableError("Fila de relatos indisponível.") from None

    async def backfill_history(self, game_id):
        """Importa uma vez as transcrições anteriores ao outbox, sem alterar a origem."""
        async with self.lease(game_id) as acquired:
            if not acquired:
                return False
            return await self._backfill_history(game_id)

    async def _backfill_history(self, game_id):
        base = self._base(game_id)
        marker, outbox = f"{base}:social:history_imported", f"{base}:social:exchanges"
        index, lease_key = f"{base}:conversations", f"{base}:social:busy"
        owner = self._owner.get()
        try:
            for _ in range(5):
                try:
                    async with self._client.pipeline() as pipe:
                        await pipe.watch(marker, outbox, index, lease_key, f"{base}:state")
                        if (owner is None or owner[0] != game_id or owner[2] is not asyncio.current_task()
                                or await pipe.get(lease_key) != owner[1]):
                            return False
                        if await pipe.exists(marker):
                            return True
                        raw_game = await pipe.get(f"{base}:state")
                        game = GameState.model_validate_json(raw_game) if raw_game is not None else None
                        if game is None or game.id != game_id:
                            raise ValueError("Caso do histórico divergente.")
                        cast = {member.character_id for member in game.characters}
                        existing = await self._read_exchanges(await pipe.lrange(outbox, 0, -1), game_id,
                                                              reader=pipe, game=game)
                        seen = {record.outgoing.id: record for record in existing}
                        pending = []
                        for raw_id in await pipe.zrange(index, 0, -1):
                            conversation_id = UUID(raw_id.decode() if isinstance(raw_id, bytes) else raw_id)
                            key = f"{base}:conversation:{conversation_id}"
                            await pipe.watch(key)
                            raw_conversation = await pipe.get(key)
                            conversation = Conversation.model_validate_json(raw_conversation) if raw_conversation is not None else None
                            if (conversation is None or conversation.id != conversation_id or conversation.game_id != game_id
                                    or not set(conversation.participant_ids).issubset(cast | {"player"})):
                                raise ValueError("Metadados do histórico divergentes.")
                            if "player" not in conversation.participant_ids:
                                continue
                            npc_id = next(identifier for identifier in conversation.participant_ids if identifier != "player")
                            order_key, messages_key = f"{key}:order", f"{key}:messages"
                            await pipe.watch(order_key, messages_key)
                            raw_order = await pipe.lrange(order_key, 0, -1)
                            order = tuple(identifier.decode() if isinstance(identifier, bytes) else identifier
                                          for identifier in raw_order)
                            if len(order) != len(set(order)) or await pipe.hlen(messages_key) != len(order):
                                raise ValueError("Índice de mensagens divergente.")
                            values = await pipe.hmget(messages_key, order) if order else ()
                            messages = tuple(ConversationMessage.model_validate_json(value) for value in values)
                            if any(str(message.id) != identifier or message.sender_id not in conversation.participant_ids
                                   for identifier, message in zip(order, messages, strict=True)):
                                raise ValueError("Mensagem do histórico divergente.")
                            for incoming, outgoing in zip(messages, messages[1:]):
                                if incoming.sender_id != "player" or outgoing.sender_id != npc_id:
                                    continue
                                record = ExchangeRecord(conversation_id=conversation_id, npc_id=npc_id, day=None,
                                                        incoming=incoming, outgoing=outgoing)
                                previous = seen.get(outgoing.id)
                                if previous is not None:
                                    if (previous.conversation_id != record.conversation_id or previous.npc_id != record.npc_id
                                            or previous.incoming != record.incoming or previous.outgoing != record.outgoing):
                                        raise ValueError("ID de resposta reutilizado no histórico.")
                                    continue
                                seen[outgoing.id] = record
                                pending.append(record)
                        pending.sort(key=lambda record: (record.incoming.created_at, record.outgoing.created_at,
                                                         str(record.conversation_id), str(record.outgoing.id)))
                        serialized = tuple(record.model_dump_json() for record in pending)
                        pipe.multi()
                        if serialized:
                            pipe.rpush(outbox, *serialized)
                        pipe.set(marker, "1")
                        await pipe.execute()
                        return True
                except WatchError:
                    continue
            return False
        except (RedisError, ValidationError, ValueError, TypeError, StopIteration):
            raise StorageUnavailableError("Migração de histórico social indisponível.") from None

    async def active_game_ids(self):
        try:
            ids = await self._client.zrange(f"{self._prefix}:games", 0, -1)
            active = []
            for value in ids:
                game_id = UUID(value.decode() if isinstance(value, bytes) else value)
                raw = await self._client.get(f"{self._base(game_id)}:state")
                if raw is not None:
                    game = GameState.model_validate_json(raw)
                    if game.id != game_id:
                        raise ValueError("Identidade divergente.")
                    if game.status == "active":
                        active.append(game_id)
                    else:
                        raw_social = await self._client.get(f"{self._base(game_id)}:social")
                        social = self._decode(raw_social, SocialState, game_id) if raw_social is not None else None
                        if social is not None and any(encounter.phase in ("travelling", "talking")
                                                      for encounter in social.encounters):
                            active.append(game_id)  # Worker só limpa reservas de encontros interrompidos pelo desfecho.
            return tuple(active)
        except (RedisError, ValidationError, ValueError, TypeError):
            raise StorageUnavailableError("Agenda social indisponível.") from None

    @asynccontextmanager
    async def lease(self, game_id):
        key = f"{self._base(game_id)}:social:busy"
        previous = self._owner.get()
        try:
            if previous and previous[0] == game_id and previous[2] is asyncio.current_task():
                yield await self._client.get(key) == previous[1]
                return
            token = uuid4().hex
            acquired = await self._client.set(key, token, nx=True, ex=self._lease_seconds)
        except RedisError:
            raise StorageUnavailableError("Reserva social indisponível.") from None
        if not acquired:
            yield False
            return
        context_token = self._owner.set((game_id, token, asyncio.current_task()))
        try:
            yield True
        finally:
            self._owner.reset(context_token)
            try:
                for _ in range(3):
                    try:
                        async with self._client.pipeline() as pipe:
                            await pipe.watch(key)
                            if await pipe.get(key) != token:
                                break
                            pipe.multi()
                            pipe.delete(key)
                            await pipe.execute()
                            break
                    except WatchError:
                        continue
            except RedisError:
                pass  # TTL recupera uma reserva abandonada.

    async def save(self, state, expected_revision, *, world=None, expected_world_revision=None,
                   require_day=None, require_npcs=(), require_player_idle=False, events=()):
        state = SocialState.model_validate(state.model_dump())
        if state.revision != expected_revision + 1:
            raise ValueError("A revisão social deve avançar exatamente uma posição.")
        if world is not None:
            world = WorldState.model_validate(world.model_dump())
            if world.game_id != state.game_id or expected_world_revision is None or world.revision != expected_world_revision + 1:
                raise ValueError("Revisão ou identidade do mundo inválida.")
        base = self._base(state.game_id)
        key, lease_key = f"{base}:social", f"{base}:social:busy"
        owner = self._owner.get()
        serialized_events = tuple(json.dumps(event, ensure_ascii=False) for event in events)
        watch = [key, lease_key, f"{base}:state", f"{base}:investigation", f"{base}:world", f"{base}:player:busy"]
        if require_npcs and require_day is not None:
            watch.append(f"{base}:social:exchanges")
        if events:
            watch.append(f"{base}:events")
        try:
            for _ in range(5):
                try:
                    async with self._client.pipeline() as pipe:
                        await pipe.watch(*watch)
                        if owner and (owner[0] != state.game_id or owner[2] is not asyncio.current_task()
                                      or await pipe.get(lease_key) != owner[1]):
                            return False
                        raw = await pipe.get(key)
                        current = self._decode(raw, SocialState, state.game_id) if raw is not None else SocialState(game_id=state.game_id)
                        if current.revision != expected_revision:
                            return False
                        if require_player_idle and await pipe.exists(f"{base}:player:busy"):
                            return False
                        raw_game = await pipe.get(f"{base}:state")
                        game = GameState.model_validate_json(raw_game) if raw_game is not None else None
                        if game is None or game.id != state.game_id:
                            return False
                        raw_case = await pipe.get(f"{base}:investigation")
                        case = self._decode(raw_case, InvestigationState, state.game_id) if raw_case is not None else None
                        if require_day is not None and (game.status != "active" or case is None or case.day != require_day
                                or case.phase != "day" or case.status != "active" or self._clock() >= case.phase_ends_at):
                            return False
                        raw_world = await pipe.get(f"{base}:world")
                        current_world = self._decode(raw_world, WorldState, state.game_id) if raw_world is not None else None
                        if expected_world_revision is not None and (current_world is None or current_world.revision != expected_world_revision):
                            return False
                        cast = {member.character_id: member for member in game.characters}
                        if any(npc not in cast or not cast[npc].alive or case and case.detained_npc_id == npc
                               for npc in require_npcs):
                            return False
                        if require_npcs and require_day is not None:
                            pending_raw = await pipe.lrange(f"{base}:social:exchanges", state.exchange_cursor, -1)
                            pending = await self._read_exchanges(pending_raw, state.game_id, reader=pipe, game=game)
                            if any(record.npc_id in require_npcs for record in pending):
                                return False
                        candidate_world = world or current_world
                        for encounter in state.encounters:
                            if encounter.phase != "talking" or not set(encounter.participant_ids).issubset(require_npcs):
                                continue
                            positions = {npc.npc_id: npc for npc in candidate_world.npcs} if candidate_world else {}
                            if any(npc not in positions or positions[npc].location_id != encounter.location_id
                                   for npc in encounter.participant_ids):
                                return False
                        if events:
                            await pipe.llen(f"{base}:events")
                        pipe.multi()
                        pipe.set(key, state.model_dump_json())
                        if world is not None:
                            pipe.set(f"{base}:world", world.model_dump_json())
                        if events:
                            pipe.rpush(f"{base}:events", *serialized_events)
                        await pipe.execute()
                        return True
                except WatchError:
                    continue
            return False
        except (RedisError, ValidationError, ValueError, TypeError):
            raise StorageUnavailableError("Persistência social indisponível.") from None
