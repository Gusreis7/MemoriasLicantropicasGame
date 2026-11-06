"""Ponto único de composição. Construir clientes não abre conexões externas."""

from dataclasses import dataclass
import logging

from redis.asyncio import Redis

from src.infrastructure.llm.bedrock_mantle import BedrockMantleClient
from src.infrastructure.llm.aws_credentials import ProfileTokenProvider
from src.infrastructure.conversation_gate import RedisConversationGate
from src.infrastructure.redis_repository import (
    RedisGameRepository,
    RedisMemoryRepository,
)
from src.modules.agents.service import HarnessService
from src.modules.agents.trace import RedisDialogueTraceRecorder
from src.modules.session_master.service import SessionMasterService
from src.modules.characters.repository import CatalogCharacterRepository
from src.modules.characters.service import CharacterService
from src.modules.games.service import GameService
from src.modules.conversations.service import ConversationService
from src.settings import Settings
from src.modules.world.repository import RedisWorldRepository
from src.modules.world.service import WorldService
from src.modules.world.gate import RedisPlayerGate
from src.modules.admin.auth import AdminAuth
from src.modules.admin.service import AdminService
from src.modules.turns.service import TurnService
from src.modules.investigation.service import InvestigationService
from src.infrastructure.social_repository import RedisSocialRepository
from src.modules.knowledge.service import KnowledgeService
from src.modules.social.service import SocialService
from src.modules.social.worker import SocialWorker
from src.modules.social.views import SocialReadService
from src.infrastructure.usage import MeteredLLMClient, RedisUsageRepository, UsagePricing

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
    if not settings.aws_use_default_credentials and not settings.aws_profile and not (settings.bedrock_api_key and settings.bedrock_api_key.get_secret_value().strip()):
        logger.warning("dialogue_configuration code=llm_credentials_missing")
    redis = Redis.from_url(
        settings.redis_url, decode_responses=True,
        socket_connect_timeout=3, socket_timeout=3,
    )
    characters = CatalogCharacterRepository()
    games = RedisGameRepository(redis, prefix=settings.redis_prefix)
    memory = RedisMemoryRepository(redis, prefix=settings.redis_prefix)
    world_repository = RedisWorldRepository(redis, settings.redis_prefix)
    gate_timeout = settings.llm_turn_timeout_seconds + 15
    player_gate = RedisPlayerGate(redis, settings.redis_prefix, gate_timeout)
    turns = TurnService(redis, settings.redis_prefix, games, characters, world_repository, player_gate)
    investigation = InvestigationService(turns, characters, memory)
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
        token_provider=(ProfileTokenProvider(
                            settings.aws_profile, settings.aws_region,
                            refresh_source_dir=settings.aws_profile_source_dir,
                        )
                        if settings.aws_profile or settings.aws_use_default_credentials else None),
    )
    llm = MeteredLLMClient(raw_llm, usage, configured_model=settings.bedrock_model)
    social_repository = RedisSocialRepository(redis, settings.redis_prefix)
    def social_client(max_tokens, timeout_seconds=12):
        raw = BedrockMantleClient(
            base_url=settings.mantle_base_url,
            api_key=settings.bedrock_api_key.get_secret_value() if settings.bedrock_api_key else None,
            model=settings.bedrock_model, timeout_seconds=timeout_seconds, max_tokens=max_tokens,
            token_provider=(ProfileTokenProvider(
                                settings.aws_profile, settings.aws_region,
                                refresh_source_dir=settings.aws_profile_source_dir,
                            )
                            if settings.aws_profile or settings.aws_use_default_credentials else None),
        )
        return MeteredLLMClient(raw, usage, configured_model=settings.bedrock_model)
    speech_llm, extraction_llm = social_client(400), social_client(800)
    assembly_llm = social_client(900)
    dialogue_llm = social_client(min(240, settings.llm_max_tokens), settings.llm_timeout_seconds)
    social_clients = (speech_llm, extraction_llm, assembly_llm, dialogue_llm)
    investigation._social_repository = social_repository
    investigation._assembly_llm = assembly_llm
    knowledge = KnowledgeService(social_repository, characters, extraction_llm)
    investigation._knowledge = knowledge
    social = SocialService(social_repository, knowledge, games, characters, world_repository,
                           turns, speech_llm, player_gate, enabled=settings.social_enabled)
    worker = SocialWorker(social, social_repository, interval_seconds=settings.social_poll_seconds)
    world = WorldService(games, characters, world_repository, player_gate, day_policy=turns,
                         on_approach=social.interrupt if social else None, social_repository=social_repository)
    master_llm = social_client(640, settings.llm_timeout_seconds)
    social_clients = (*social_clients, master_llm)
    master = SessionMasterService(turns, games, memory, master_llm, redis, settings.redis_prefix)
    turns._victory_editor = master.publish_victory
    from src.modules.table.service import GameTableService
    table_service = GameTableService(turns, characters, knowledge)
    harness = HarnessService(characters, games, memory, dialogue_llm, history_limit=settings.llm_history_limit,
                             day_policy=turns, context_provider=investigation.npc_context_locked,
                             knowledge_provider=knowledge.context if knowledge else None, session_master=master,
                             trace_sink=RedisDialogueTraceRecorder(redis, settings.redis_prefix).record,
                             turn_timeout_seconds=settings.llm_turn_timeout_seconds, table_service=table_service)
    return Services(
        characters=CharacterService(characters),
        games=GameService(characters, games, day_policy=turns),
        harness=harness,
        redis=redis,
        llm=llm,
        conversations=ConversationService(
            characters, games, memory, harness,
            RedisConversationGate(redis, settings.redis_prefix, gate_timeout),
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
