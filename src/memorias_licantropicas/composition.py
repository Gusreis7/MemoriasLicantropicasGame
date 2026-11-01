"""Ponto único de composição. Construir clientes não abre conexões externas."""

from dataclasses import dataclass

from redis.asyncio import Redis

from memorias_licantropicas.infrastructure.llm.bedrock_mantle import BedrockMantleClient
from memorias_licantropicas.infrastructure.redis_repository import (
    RedisGameRepository,
    RedisMemoryRepository,
)
from memorias_licantropicas.modules.agents.service import HarnessService
from memorias_licantropicas.modules.characters.repository import CatalogCharacterRepository
from memorias_licantropicas.modules.characters.service import CharacterService
from memorias_licantropicas.modules.games.service import GameService
from memorias_licantropicas.settings import Settings


@dataclass(frozen=True)
class Services:
    characters: CharacterService
    games: GameService
    harness: HarnessService
    redis: Redis
    llm: BedrockMantleClient

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
    llm = BedrockMantleClient(
        base_url=settings.mantle_base_url,
        api_key=settings.bedrock_api_key.get_secret_value() if settings.bedrock_api_key else None,
        model=settings.bedrock_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
    )
    return Services(
        characters=CharacterService(characters),
        games=GameService(characters, games),
        harness=HarnessService(
            characters, games, memory, llm, history_limit=settings.llm_history_limit,
        ),
        redis=redis,
        llm=llm,
    )
