"""Projeções administrativas de registros existentes, sem alterar o jogo."""

from functools import wraps
from uuid import UUID

from pydantic import ValidationError
from redis.exceptions import RedisError

from memorias_licantropicas.contracts.errors import NotFoundError, StorageUnavailableError
from memorias_licantropicas.contracts.model import Conversation, ConversationMessage
from memorias_licantropicas.contracts.investigation import InvestigationState
from memorias_licantropicas.modules.admin.schema import (
    AdminCharacter, AdminConversation, AdminMessage, AdminState, EventPublic, GameListItem,
    InteractionEdge, InteractionNode, Interactions, KnownDeath, Page,
)


def storage_errors(method):
    @wraps(method)
    async def wrapped(*args, **kwargs):
        try:
            return await method(*args, **kwargs)
        except (RedisError, ValidationError, ValueError, TypeError, KeyError):
            raise StorageUnavailableError("Consulta administrativa indisponível.") from None
    return wrapped


def _text(value):
    return value.decode() if isinstance(value, bytes) else value


class AdminService:
    def __init__(self, client, prefix, games, characters, worldrepository):
        self._client = client
        self._prefix = prefix
        self._games = games
        self._characters = characters
        self._world = worldrepository

    def _game_prefix(self, game_id):
        return f"{self._prefix}:game:{{{game_id}}}"

    async def _game(self, game_id):
        game = await self._games.get(game_id)
        if game is None:
            raise NotFoundError("Partida não encontrada.")
        return game

    async def _conversation(self, game_id, conversation_id):
        raw = await self._client.get(f"{self._game_prefix(game_id)}:conversation:{conversation_id}")
        if raw is None:
            raise NotFoundError("Conversa não encontrada.")
        conversation = Conversation.model_validate_json(raw)
        if conversation.game_id != game_id or conversation.id != conversation_id:
            raise StorageUnavailableError("Registro administrativo inválido.")
        return conversation

    async def _all_messages(self, game_id, conversation_id):
        key = f"{self._game_prefix(game_id)}:conversation:{conversation_id}"
        ids = await self._client.lrange(f"{key}:order", 0, -1)
        ids = list(dict.fromkeys(ids))
        values = await self._client.hmget(f"{key}:messages", ids) if ids else []
        messages = [ConversationMessage.model_validate_json(value) for value in values]
        if any(str(message.id) != _text(identifier) for identifier, message in zip(ids, messages, strict=True)):
            raise StorageUnavailableError("Histórico administrativo inválido.")
        return messages

    @storage_errors
    async def list_games(self, offset=0, limit=20):
        key = f"{self._prefix}:games"
        ids = await self._client.zrevrange(key, offset, offset + limit - 1)
        items = []
        for identifier in ids:
            game = await self._game(UUID(_text(identifier)))
            items.append(GameListItem(id=game.id, created_at=game.created_at, status=game.status))
        return Page[GameListItem](items=items, total=await self._client.zcard(key))

    @storage_errors
    async def state(self, game_id):
        game = await self._game(game_id)
        profiles = {profile.id: profile for profile in await self._characters.list()}
        world = await self._world.get(game_id)
        positions = {npc.npc_id: npc for npc in world.npcs} if world else {}
        names = {identifier: profile.name for identifier, profile in profiles.items()}
        names["bras_cubas"] = "Brás Cubas"
        raw_case = await self._client.get(f"{self._game_prefix(game_id)}:investigation")
        case = InvestigationState.model_validate_json(raw_case) if raw_case is not None else None
        if case is not None and case.game_id != game_id:
            raise StorageUnavailableError("Identidade administrativa inválida.")
        deaths = {"bras_cubas": KnownDeath(victim_id="bras_cubas", victim_name="Brás Cubas",
                                           killer_id=None, killer_name=None, attribution="unknown", source="scenario")}
        # Uma alegação em mensagem nunca é promovida a morte. Só fatos do futuro motor de regras.
        for raw in await self._client.lrange(f"{self._game_prefix(game_id)}:events", 0, -1):
            event = EventPublic.model_validate_json(raw)
            if event.type != "character.killed" or event.source != "rules":
                continue
            victim = event.data.get("victim_id")
            if not isinstance(victim, str):
                continue
            killer = event.data.get("killer_id")
            if killer not in names:
                killer = None
            deaths[victim] = KnownDeath(victim_id=victim, victim_name=names.get(victim, victim),
                                        killer_id=killer, killer_name=names.get(killer),
                                        attribution="known" if killer else "unknown", source="rules")
        return AdminState(
            game_id=game.id, created_at=game.created_at, content_version=game.content_version,
            status=game.status,
            werewolf_id=next(character.character_id for character in game.characters if character.role == "werewolf"),
            characters=[AdminCharacter(
                character_id=character.character_id,
                name=names.get(character.character_id, character.character_id),
                role=character.role, alive=character.alive,
                location_id=positions[character.character_id].location_id if character.character_id in positions else None,
                x=positions[character.character_id].x if character.character_id in positions else None,
            ) for character in game.characters],
            player=world.player.model_dump(mode="json") if world else None,
            known_deaths=list(deaths.values()), world_version=world.world_version if world else None,
            investigation=case.model_dump(mode="json") if case else None,
        )

    @storage_errors
    async def events(self, game_id, offset=0, limit=50):
        await self._game(game_id)
        key = f"{self._game_prefix(game_id)}:events"
        items = [EventPublic.model_validate_json(value) for value in await self._client.lrange(key, offset, offset + limit - 1)]
        return Page[EventPublic](items=items, total=await self._client.llen(key))

    @storage_errors
    async def conversations(self, game_id, offset=0, limit=50):
        await self._game(game_id)
        key = f"{self._game_prefix(game_id)}:conversations"
        ids = await self._client.zrevrange(key, offset, offset + limit - 1)
        items = []
        for identifier in ids:
            conversation = await self._conversation(game_id, UUID(_text(identifier)))
            items.append(AdminConversation.model_validate(conversation.model_dump()))
        return Page[AdminConversation](items=items, total=await self._client.zcard(key))

    @storage_errors
    async def messages(self, game_id, conversation_id, offset=0, limit=100):
        await self._game(game_id)
        conversation = await self._conversation(game_id, conversation_id)
        key = f"{self._game_prefix(game_id)}:conversation:{conversation_id}"
        ids = await self._client.lrange(f"{key}:order", offset, offset + limit - 1)
        values = await self._client.hmget(f"{key}:messages", ids) if ids else []
        messages = [ConversationMessage.model_validate_json(value) for value in values]
        if any(message.sender_id not in conversation.participant_ids for message in messages):
            raise StorageUnavailableError("Histórico administrativo inválido.")
        if any(str(message.id) != _text(identifier) for identifier, message in zip(ids, messages, strict=True)):
            raise StorageUnavailableError("Histórico administrativo inválido.")
        return Page[AdminMessage](items=[AdminMessage.model_validate(message.model_dump()) for message in messages],
                                  total=await self._client.llen(f"{key}:order"))

    @storage_errors
    async def interactions(self, game_id):
        game = await self._game(game_id)
        profiles = {profile.id: profile for profile in await self._characters.list()}
        names = {npc.character_id: profiles[npc.character_id].name for npc in game.characters}
        names["player"] = "Detetive Floriano"
        nodes = [InteractionNode(id=identifier, name=name) for identifier, name in names.items()]
        key = f"{self._game_prefix(game_id)}:conversations"
        edges = []
        for identifier in await self._client.zrange(key, 0, -1):
            conversation = await self._conversation(game_id, UUID(_text(identifier)))
            messages = await self._all_messages(game_id, conversation.id)
            if any(message.sender_id not in conversation.participant_ids for message in messages):
                raise StorageUnavailableError("Histórico administrativo inválido.")
            # Uma conversa vazia não representa uma interação concluída.
            if messages:
                edges.append(InteractionEdge(source=conversation.participant_ids[0], target=conversation.participant_ids[1],
                                              message_count=len(messages), last_at=messages[-1].created_at,
                                              conversation_id=conversation.id))
        return Interactions(nodes=nodes, edges=edges)

    async def health(self):
        try:
            await self._client.ping()
            return {"redis": "ok"}
        except RedisError:
            return {"redis": "unavailable"}
