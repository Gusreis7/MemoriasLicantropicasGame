"""Persistência Redis dos contratos internos v1, sem dependência de HTTP."""

from typing import TypeVar
from uuid import UUID

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError, WatchError

from memorias_licantropicas.contracts.errors import (
    AccessDeniedError,
    ConflictError,
    NotFoundError,
    StorageUnavailableError,
)
from memorias_licantropicas.contracts.model import (
    Contract,
    Conversation,
    ConversationMessage,
    GameState,
)

_Model = TypeVar("_Model", bound=Contract)
_MAX_TRANSACTION_ATTEMPTS = 5
_MAX_HISTORY_LIMIT = 200


def _decode(value: str | bytes, model: type[_Model]) -> _Model:
    try:
        return model.model_validate_json(value)
    except (ValidationError, ValueError, TypeError):
        raise StorageUnavailableError("Registro persistido inválido.") from None


class _RedisRepository:
    def __init__(self, client: Redis, prefix: str = "ml:v1") -> None:
        if not prefix or "{" in prefix or "}" in prefix:
            raise ValueError("Prefixo Redis deve ser não vazio e não conter chaves.")
        self._client = client
        self._prefix = prefix

    def _game_key(self, game_id: UUID) -> str:
        # Hash tag comum permite agrupar chaves da partida num mesmo slot Redis.
        return f"{self._prefix}:game:{{{game_id}}}:state"

    def _conversation_key(self, game_id: UUID, conversation_id: UUID) -> str:
        return f"{self._prefix}:game:{{{game_id}}}:conversation:{conversation_id}"

    @staticmethod
    def _read_conversation(
        value: str | bytes | None, game_id: UUID, conversation_id: UUID,
    ) -> Conversation | None:
        if value is None:
            return None
        conversation = _decode(value, Conversation)
        if conversation.game_id != game_id or conversation.id != conversation_id:
            raise StorageUnavailableError("Identidade de conversa persistida inválida.")
        return conversation


class RedisGameRepository(_RedisRepository):
    """Partidas insert-only; o sorteio existente jamais é sobrescrito."""

    async def create(self, game: GameState) -> bool:
        try:
            return bool(await self._client.set(
                self._game_key(game.id), game.model_dump_json(), nx=True,
            ))
        except RedisError:
            raise StorageUnavailableError("Persistência indisponível.") from None

    async def get(self, game_id: UUID) -> GameState | None:
        try:
            value = await self._client.get(self._game_key(game_id))
        except RedisError:
            raise StorageUnavailableError("Persistência indisponível.") from None
        if value is None:
            return None
        game = _decode(value, GameState)
        if game.id != game_id:
            raise StorageUnavailableError("Identidade de partida persistida inválida.")
        return game


class RedisMemoryRepository(_RedisRepository):
    """Conversas privadas e mensagens append-only com lotes atômicos."""

    async def create_conversation(self, conversation: Conversation) -> bool:
        game_key = self._game_key(conversation.game_id)
        key = self._conversation_key(conversation.game_id, conversation.id)
        try:
            for _ in range(_MAX_TRANSACTION_ATTEMPTS):
                try:
                    async with self._client.pipeline(transaction=True) as pipe:
                        await pipe.watch(game_key, key)
                        if await pipe.exists(key):
                            return False
                        raw_game = await pipe.get(game_key)
                        if raw_game is None:
                            raise NotFoundError("Partida não encontrada.")
                        game = _decode(raw_game, GameState)
                        if game.id != conversation.game_id:
                            raise StorageUnavailableError("Identidade de partida persistida inválida.")
                        allowed = {"player"} | {
                            character.character_id for character in game.characters if character.alive
                        }
                        if not set(conversation.participant_ids) <= allowed:
                            raise AccessDeniedError("Participante indisponível nesta partida.")
                        pipe.multi()
                        pipe.set(key, conversation.model_dump_json(), nx=True)
                        result = await pipe.execute()
                        return bool(result[0])
                except WatchError:
                    continue
        except RedisError:
            raise StorageUnavailableError("Persistência indisponível.") from None
        raise ConflictError("Conversa alterada concorrentemente; tente novamente.")

    async def get_conversation(
        self, game_id: UUID, conversation_id: UUID,
    ) -> Conversation | None:
        try:
            value = await self._client.get(self._conversation_key(game_id, conversation_id))
        except RedisError:
            raise StorageUnavailableError("Persistência indisponível.") from None
        return self._read_conversation(value, game_id, conversation_id)

    async def append_messages(
        self, game_id: UUID, conversation_id: UUID,
        messages: tuple[ConversationMessage, ...],
    ) -> None:
        # Duplicatas dentro do próprio lote seguem a mesma regra das já persistidas.
        batch: dict[str, ConversationMessage] = {}
        for message in messages:
            message_id = str(message.id)
            if message_id in batch and batch[message_id] != message:
                raise ConflictError("ID de mensagem reutilizado com conteúdo diferente.")
            batch[message_id] = message

        key = self._conversation_key(game_id, conversation_id)
        records_key = f"{key}:messages"
        order_key = f"{key}:order"
        try:
            for _ in range(_MAX_TRANSACTION_ATTEMPTS):
                try:
                    async with self._client.pipeline(transaction=True) as pipe:
                        await pipe.watch(key, records_key, order_key)
                        conversation = self._read_conversation(
                            await pipe.get(key), game_id, conversation_id,
                        )
                        if conversation is None:
                            raise NotFoundError("Conversa não encontrada.")
                        if any(
                            message.sender_id not in conversation.participant_ids
                            for message in batch.values()
                        ):
                            raise AccessDeniedError("Remetente não participa da conversa.")
                        if not batch:
                            return
                        existing = await pipe.hmget(records_key, list(batch))
                        # Detecta tipo inválido antes do MULTI: Redis não faz rollback
                        # de comandos bem-sucedidos se outro comando da transação falhar.
                        await pipe.llen(order_key)
                        pending: dict[str, str] = {}
                        for (message_id, message), value in zip(batch.items(), existing, strict=True):
                            if value is None:
                                pending[message_id] = message.model_dump_json()
                            elif _decode(value, ConversationMessage) != message:
                                raise ConflictError("ID de mensagem reutilizado com conteúdo diferente.")
                        if not pending:
                            return
                        pipe.multi()
                        pipe.hset(records_key, mapping=pending)
                        pipe.rpush(order_key, *pending)
                        await pipe.execute()
                        return
                except WatchError:
                    continue
        except RedisError:
            raise StorageUnavailableError("Persistência indisponível.") from None
        raise ConflictError("Histórico alterado concorrentemente; tente novamente.")

    async def list_messages(
        self, game_id: UUID, conversation_id: UUID, viewer_id: str, limit: int = 20,
    ) -> tuple[ConversationMessage, ...]:
        if not 1 <= limit <= _MAX_HISTORY_LIMIT:
            raise ValueError(f"Limite de histórico deve estar entre 1 e {_MAX_HISTORY_LIMIT}.")
        key = self._conversation_key(game_id, conversation_id)
        records_key = f"{key}:messages"
        order_key = f"{key}:order"
        try:
            for _ in range(_MAX_TRANSACTION_ATTEMPTS):
                try:
                    async with self._client.pipeline(transaction=True) as pipe:
                        await pipe.watch(key, records_key, order_key)
                        conversation = self._read_conversation(
                            await pipe.get(key), game_id, conversation_id,
                        )
                        if conversation is None:
                            raise NotFoundError("Conversa não encontrada.")
                        if viewer_id not in conversation.participant_ids:
                            raise AccessDeniedError("Leitura restrita aos participantes da conversa.")
                        ids = await pipe.lrange(order_key, -limit, -1)
                        values = await pipe.hmget(records_key, ids) if ids else []
                        # EXEC vazio confirma que a leitura observou um único snapshot.
                        pipe.multi()
                        await pipe.execute()
                        if any(value is None for value in values):
                            raise StorageUnavailableError("Histórico persistido inconsistente.")
                        result = tuple(_decode(value, ConversationMessage) for value in values)
                        if any(message.sender_id not in conversation.participant_ids for message in result):
                            raise StorageUnavailableError("Histórico persistido inconsistente.")
                        decoded_ids = tuple(
                            message_id.decode() if isinstance(message_id, bytes) else message_id
                            for message_id in ids
                        )
                        if any(
                            str(message.id) != message_id
                            for message_id, message in zip(decoded_ids, result, strict=True)
                        ):
                            raise StorageUnavailableError("Histórico persistido inconsistente.")
                        return result
                except WatchError:
                    continue
        except RedisError:
            raise StorageUnavailableError("Persistência indisponível.") from None
        raise ConflictError("Histórico alterado concorrentemente; tente novamente.")
