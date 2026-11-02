"""Ponto único de composição. Construir clientes não abre conexões externas."""

from dataclasses import dataclass
import logging

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
from memorias_licantropicas.infrastructure.social_repository import RedisSocialRepository
from memorias_licantropicas.modules.knowledge.service import KnowledgeService
from memorias_licantropicas.modules.social.service import SocialService
from memorias_licantropicas.modules.social.worker import SocialWorker
from memorias_licantropicas.modules.social.views import SocialReadService
from memorias_licantropicas.infrastructure.usage import MeteredLLMClient, RedisUsageRepository, UsagePricing

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Services:
    characters: CharacterService
    games: GameService
    harness: HarnessService
    redis: Redis
    llm: BedrockMantleClient | MeteredLLMClient
    conversations: ConversationService
    world: WorldService
    admin_auth: AdminAuth
    admin: AdminService
    turns: TurnService
    investigation: InvestigationService
    knowledge: KnowledgeService | None = None
    social: SocialService | None = None
    social_worker: SocialWorker | None = None
    social_reads: SocialReadService | None = None
    social_clients: tuple[BedrockMantleClient | MeteredLLMClient, ...] = ()
    usage: RedisUsageRepository | None = None

    async def aclose(self) -> None:
        try:
            if self.social_worker is not None:
                await self.social_worker.stop()
        finally:
            try:
                for client in (*self.social_clients, self.llm):
                    await client.aclose()
            finally:
                await self.redis.aclose()


def build_services(settings: Settings) -> Services:
    if not settings.aws_profile and not (settings.bedrock_api_key and settings.bedrock_api_key.get_secret_value().strip()):
        logger.warning("dialogue_configuration code=llm_credentials_missing")
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
    investigation = InvestigationService(turns, characters)
    pricing_matches = (settings.bedrock_model == settings.llm_pricing_model
                       and settings.aws_region == settings.llm_pricing_region)
    usage = RedisUsageRepository(redis, settings.redis_prefix, pricing=UsagePricing(
        model=settings.llm_pricing_model,
        input_usd_per_million=settings.llm_input_usd_per_million if pricing_matches else None,
        output_usd_per_million=settings.llm_output_usd_per_million if pricing_matches else None,
        source=settings.llm_pricing_source, checked_at=settings.llm_pricing_checked_at,
    ))
    raw_llm = BedrockMantleClient(
        base_url=settings.mantle_base_url,
        api_key=settings.bedrock_api_key.get_secret_value() if settings.bedrock_api_key else None,
        model=settings.bedrock_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
        token_provider=(ProfileTokenProvider(settings.aws_profile, settings.aws_region)
                        if settings.aws_profile else None),
    )
    llm = MeteredLLMClient(raw_llm, usage, configured_model=settings.bedrock_model)
    social_repository = RedisSocialRepository(redis, settings.redis_prefix)
    def social_client(max_tokens):
        raw = BedrockMantleClient(
            base_url=settings.mantle_base_url,
            api_key=settings.bedrock_api_key.get_secret_value() if settings.bedrock_api_key else None,
            model=settings.bedrock_model, timeout_seconds=12, max_tokens=max_tokens,
            token_provider=(ProfileTokenProvider(settings.aws_profile, settings.aws_region)
                            if settings.aws_profile else None),
        )
        return MeteredLLMClient(raw, usage, configured_model=settings.bedrock_model)
    speech_llm, extraction_llm = social_client(400), social_client(800)
    social_clients = (speech_llm, extraction_llm)
    knowledge = KnowledgeService(social_repository, characters, extraction_llm)
    social = SocialService(social_repository, knowledge, games, characters, world_repository,
                           turns, speech_llm, player_gate, enabled=settings.social_enabled)
    worker = SocialWorker(social, social_repository, interval_seconds=settings.social_poll_seconds)
    world = WorldService(games, characters, world_repository, player_gate, day_policy=turns,
                         on_approach=social.interrupt if social else None, social_repository=social_repository)
    harness = HarnessService(characters, games, memory, llm, history_limit=settings.llm_history_limit,
                             day_policy=turns, context_provider=investigation.npc_context_locked,
                             knowledge_provider=knowledge.context if knowledge else None)
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
        admin=AdminService(redis, settings.redis_prefix, games, characters, world_repository,
                           turns=turns, social_repository=social_repository, usage_repository=usage),
        turns=turns,
        investigation=investigation,
        knowledge=knowledge, social=social, social_worker=worker,
        social_reads=SocialReadService(social_repository, games, characters), social_clients=social_clients,
        usage=usage,
    )
