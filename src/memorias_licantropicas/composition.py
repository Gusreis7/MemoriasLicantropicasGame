"""Ponto único de composição. Construir clientes não abre conexões externas."""

from dataclasses import dataclass

from redis.asyncio import Redis

from memorias_licantropicas.infrastructure.llm.bedrock_mantle import BedrockMantleClient
from memorias_licantropicas.infrastructure.llm.aws_credentials import ProfileTokenProvider
from memorias_licantropicas.infrastructure.conversation_gate import RedisConversationGate
from memorias_licantropicas.infrastructure.redis_repository import (
    RedisGameRepository,
    RedisMemoryRepository,
)
from memorias_licantropicas.modules.agents.service import HarnessService
from memorias_licantropicas.modules.characters.repository import CatalogCharacterRepository
from memorias_licantropicas.modules.characters.service import CharacterService
from memorias_licantropicas.modules.games.service import GameService
from memorias_licantropicas.modules.conversations.service import ConversationService
from memorias_licantropicas.settings import Settings
from memorias_licantropicas.modules.world.repository import RedisWorldRepository
from memorias_licantropicas.modules.world.service import WorldService
from memorias_licantropicas.modules.world.gate import RedisPlayerGate
from memorias_licantropicas.modules.admin.auth import AdminAuth
from memorias_licantropicas.modules.admin.service import AdminService
from memorias_licantropicas.modules.turns.service import TurnService
from memorias_licantropicas.modules.investigation.service import InvestigationService


@dataclass(frozen=True)
class Services:
    characters: CharacterService
    games: GameService
    harness: HarnessService
    redis: Redis
    llm: BedrockMantleClient
    conversations: ConversationService
    world: WorldService
    admin_auth: AdminAuth
    admin: AdminService
    turns: TurnService
    investigation: InvestigationService

    async def aclose(self) -> None:
        try:
            await self.llm.aclose()
        finally:
            await self.redis.aclose()


def build_services(settings: Settings) -> Services:
    redis = Redis.from_url(
        settings.redis_url, decode_responses=True,
        socket_connect_timeout=3, socket_timeout=3,
    )
    characters = CatalogCharacterRepository()
    games = RedisGameRepository(redis, prefix=settings.redis_prefix)
    memory = RedisMemoryRepository(redis, prefix=settings.redis_prefix)
    world_repository = RedisWorldRepository(redis, settings.redis_prefix)
    player_gate = RedisPlayerGate(redis, settings.redis_prefix, settings.llm_timeout_seconds + 10)
    turns = TurnService(redis, settings.redis_prefix, games, characters, world_repository, player_gate)
    world = WorldService(games, characters, world_repository, player_gate, day_policy=turns)
    investigation = InvestigationService(turns, characters)
    llm = BedrockMantleClient(
        base_url=settings.mantle_base_url,
        api_key=settings.bedrock_api_key.get_secret_value() if settings.bedrock_api_key else None,
        model=settings.bedrock_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
        token_provider=(ProfileTokenProvider(settings.aws_profile, settings.aws_region)
                        if settings.aws_profile else None),
    )
    harness = HarnessService(characters, games, memory, llm, history_limit=settings.llm_history_limit,
                             day_policy=turns, context_provider=investigation.npc_context_locked)
    return Services(
        characters=CharacterService(characters),
        games=GameService(characters, games, day_policy=turns),
        harness=harness,
        redis=redis,
        llm=llm,
        conversations=ConversationService(
            characters, games, memory, harness,
            RedisConversationGate(redis, settings.redis_prefix, settings.llm_timeout_seconds + 10),
            world, player_gate,
        ),
        world=world,
        admin_auth=AdminAuth(redis, settings.redis_prefix, settings),
        admin=AdminService(redis, settings.redis_prefix, games, characters, world_repository, turns=turns),
        turns=turns,
        investigation=investigation,
    )
