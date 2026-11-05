"""Fixtures isoladas: nenhum flush global ou chamada AWS."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import fakeredis
import httpx
import pytest
from native_fixtures import respond_to_tools
from redis.asyncio import Redis

import memorias_licantropicas.main as main_module
from memorias_licantropicas.composition import Services
from memorias_licantropicas.contracts.model import (
    Conversation,
    ConversationMessage,
    GameCharacter,
    GameState,
    LLMResponse,
)
from memorias_licantropicas.infrastructure.redis_repository import (
    RedisGameRepository,
    RedisMemoryRepository,
)
from memorias_licantropicas.modules.agents.service import HarnessService
from memorias_licantropicas.modules.characters.repository import (
    CatalogCharacterRepository,
)
from memorias_licantropicas.modules.characters.service import CharacterService
from memorias_licantropicas.modules.games.service import GameService
from memorias_licantropicas.modules.conversations.service import ConversationService
from memorias_licantropicas.infrastructure.conversation_gate import (
    RedisConversationGate,
)
from memorias_licantropicas.modules.world.repository import RedisWorldRepository
from memorias_licantropicas.modules.world.service import WorldService
from memorias_licantropicas.modules.world.gate import RedisPlayerGate
from memorias_licantropicas.modules.admin.auth import AdminAuth
from memorias_licantropicas.modules.admin.service import AdminService
from memorias_licantropicas.modules.turns.service import TurnService
from memorias_licantropicas.modules.investigation.service import InvestigationService
from memorias_licantropicas.settings import Settings


def pytest_addoption(parser):
    parser.addoption(
        "--redis-url",
        default=os.environ.get("TEST_REDIS_URL"),
        help="Redis real opcional; namespace exclusivo por teste.",
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def prevent_external_http(monkeypatch):
    original = httpx.AsyncClient.send

    async def guarded_send(self, request, *args, **kwargs):
        if not isinstance(self._transport, (httpx.ASGITransport, httpx.MockTransport)):
            raise AssertionError("Testes não podem acessar HTTP externo/AWS.")
        return await original(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", guarded_send)


@dataclass
class Storage:
    client: Redis
    prefix: str
    games: RedisGameRepository
    memory: RedisMemoryRepository
    server: object | None = None


@pytest.fixture
async def storage(request, anyio_backend):
    url = request.config.getoption("--redis-url")
    server = None if url else fakeredis.FakeServer()
    client = (
        Redis.from_url(
            url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        if url
        else fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    )
    prefix = f"ml:test:{uuid4().hex}"
    try:
        await client.ping()
        yield Storage(
            client,
            prefix,
            RedisGameRepository(client, prefix),
            RedisMemoryRepository(client, prefix),
            server,
        )
    finally:
        try:
            keys = [key async for key in client.scan_iter(match=f"{prefix}:*")]
            if keys:
                await client.delete(*keys)
        finally:
            await client.aclose()


@pytest.fixture
def catalog():
    return CatalogCharacterRepository()


@pytest.fixture
def game():
    return GameState(
        id=uuid4(),
        created_at=datetime.now(UTC),
        characters=(
            GameCharacter(character_id="bentinho", role="werewolf"),
            GameCharacter(character_id="capitu", role="civil"),
            GameCharacter(character_id="escobar", role="civil"),
        ),
        content_version="3",
    )


@pytest.fixture
async def conversation(storage, game):
    await storage.games.create(game)
    result = Conversation(
        id=uuid4(),
        game_id=game.id,
        participant_ids=("player", "bentinho"),
        created_at=datetime.now(UTC),
    )
    await storage.memory.create_conversation(result)
    return result


@pytest.fixture
def message_factory():
    def create(content="O que viu ontem?", sender_id="player"):
        return ConversationMessage(
            id=uuid4(),
            sender_id=sender_id,
            content=content,
            created_at=datetime.now(UTC),
        )

    return create


class StubLLM:
    def __init__(self):
        self.calls = []
        self.error = None
        self.closed = False

    async def complete(self, messages, *, tools=(), tool_choice=None):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return respond_to_tools(
            {"fala": "Sei apenas o que me contaram."},
            tools,
            tool_choice,
            model="stub",
            input_tokens=10,
            output_tokens=8,
        )

    async def aclose(self):
        self.closed = True


@pytest.fixture
def llm():
    return StubLLM()


@pytest.fixture
def harness(catalog, storage, llm):
    return HarnessService(catalog, storage.games, storage.memory, llm)


@pytest.fixture
async def api_client(monkeypatch, catalog, storage, llm):
    settings = Settings(_env_file=None, admin_password="test-admin-password")
    world_repository = RedisWorldRepository(storage.client, storage.prefix)
    player_gate = RedisPlayerGate(storage.client, storage.prefix)
    turns = TurnService(
        storage.client,
        storage.prefix,
        storage.games,
        catalog,
        world_repository,
        player_gate,
    )
    investigation = InvestigationService(turns, catalog)
    world = WorldService(
        storage.games, catalog, world_repository, player_gate, day_policy=turns
    )
    case_harness = HarnessService(
        catalog,
        storage.games,
        storage.memory,
        llm,
        day_policy=turns,
        context_provider=investigation.npc_context_locked,
    )
    services = Services(
        characters=CharacterService(catalog),
        games=GameService(catalog, storage.games, day_policy=turns),
        harness=case_harness,
        redis=storage.client,
        llm=llm,
        conversations=ConversationService(
            catalog,
            storage.games,
            storage.memory,
            case_harness,
            RedisConversationGate(storage.client, storage.prefix),
            world,
            player_gate,
        ),
        world=world,
        admin_auth=AdminAuth(storage.client, storage.prefix, settings),
        admin=AdminService(
            storage.client,
            storage.prefix,
            storage.games,
            catalog,
            world_repository,
            turns=turns,
        ),
        turns=turns,
        investigation=investigation,
    )
    monkeypatch.setattr(main_module, "build_services", lambda settings: services)
    monkeypatch.setattr(main_module, "Settings", lambda: settings)
    app = main_module.create_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


@pytest.fixture
def single_wolf_attack(monkeypatch):
    """Cenário de regressão com um ataque; os testes v4 exercitam as demais noites."""
    monkeypatch.setattr(
        "memorias_licantropicas.modules.investigation.night_story.roll",
        lambda story, night, channel: 0.0 if channel == "werewolf" else 1.0,
    )
