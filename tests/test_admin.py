import asyncio
import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import SecretStr

from src.contracts.errors import NotFoundError, StorageUnavailableError
from src.modules.admin.auth import AdminAuth, COOKIE_NAME
from src.modules.admin.router import router
from src.modules.admin.service import AdminService
from src.modules.world.catalog import make_initial_world
from src.modules.world.repository import RedisWorldRepository

pytestmark = pytest.mark.anyio
PASSWORD = "only-for-tests-strong-password"


@pytest.fixture
def admin_settings():
    return SimpleNamespace(admin_username="admin", admin_password=SecretStr(PASSWORD),
                           admin_session_seconds=3600, admin_cookie_secure=False,
                           admin_allowed_origins="http://test,http://localhost:7078")


@pytest.fixture
def admin_app(storage, catalog, admin_settings):
    app = FastAPI()
    app.state.services = SimpleNamespace(
        admin_auth=AdminAuth(storage.client, storage.prefix, admin_settings),
        admin=AdminService(storage.client, storage.prefix, storage.games, catalog,
                           RedisWorldRepository(storage.client, storage.prefix)),
    )
    app.include_router(router)

    async def missing(request: Request, error):
        return JSONResponse({"detail": "Recurso não encontrado."}, status_code=404)

    async def unavailable(request: Request, error):
        return JSONResponse({"detail": "Integração indisponível."}, status_code=503)

    app.add_exception_handler(NotFoundError, missing)
    app.add_exception_handler(StorageUnavailableError, unavailable)
    return app


@pytest.fixture
async def admin_client(admin_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=admin_app), base_url="http://test") as client:
        yield client


async def login(client, username="admin", password=PASSWORD, **kwargs):
    return await client.post("/admin/api/v1/auth/login", json={"username": username, "password": password}, **kwargs)


@pytest.fixture
async def authorized_client(admin_client):
    response = await login(admin_client)
    assert response.status_code == 200
    return admin_client


@pytest.fixture
async def admin_seed(storage, game, conversation):
    prefix = f"{storage.prefix}:game:{{{game.id}}}"
    await RedisWorldRepository(storage.client, storage.prefix).create(make_initial_world(game.id))
    await storage.client.zadd(f"{storage.prefix}:games", {str(game.id): game.created_at.timestamp()})
    await storage.client.zadd(f"{prefix}:conversations", {str(conversation.id): conversation.created_at.timestamp()})
    await storage.client.rpush(f"{prefix}:events", json.dumps({
        "id": "known-initial-death", "type": "story.initial_death", "source": "scenario",
        "occurred_at": datetime.now(UTC).isoformat(),
        "data": {"victim_id": "bras_cubas", "killer_id": None, "attribution": "unknown"},
    }))
    return game, conversation


@pytest.mark.parametrize("path", [
    "/games", "/health", "/auth/session", f"/games/{uuid4()}/state", f"/games/{uuid4()}/events",
    f"/games/{uuid4()}/conversations", f"/games/{uuid4()}/interactions",
    f"/games/{uuid4()}/conversations/{uuid4()}/messages",
])
async def test_every_admin_read_requires_session(admin_client, path):
    assert (await admin_client.get(f"/admin/api/v1{path}")).status_code == 401


async def test_login_cookie_session_and_logout(admin_client, storage):
    response = await login(admin_client, headers={"Origin": "http://test"})
    assert response.status_code == 200
    assert response.json() == {"username": "admin"}
    assert response.headers["cache-control"] == "no-store"
    header = response.headers["set-cookie"]
    assert "HttpOnly" in header and "SameSite=strict" in header and "Path=/admin/api" in header
    token = response.cookies[COOKIE_NAME]
    key = f"{storage.prefix}:admin:session:{hashlib.sha256(token.encode()).hexdigest()}"
    raw = await storage.client.get(key)
    assert token not in raw and PASSWORD not in raw
    assert 0 < await storage.client.ttl(key) <= 3600
    assert (await admin_client.get("/admin/api/v1/auth/session")).json() == {"username": "admin"}
    assert (await admin_client.post("/admin/api/v1/auth/logout", headers={"Origin": "http://test"})).status_code == 200
    assert await storage.client.get(key) is None
    assert (await admin_client.get("/admin/api/v1/auth/session", headers={"Cookie": f"{COOKIE_NAME}={token}"})).status_code == 401


async def test_wrong_credentials_are_generic_and_rate_limited(admin_client):
    for attempt in range(10):
        response = await login(admin_client, username="unknown" if attempt % 2 else "admin", password="wrong")
        assert response.status_code == 401
        assert response.json() == {"detail": "Usuário ou senha inválidos."}
        assert "set-cookie" not in response.headers
    response = await login(admin_client)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "300"


async def test_expired_session_is_rejected(admin_client, storage):
    response = await login(admin_client)
    token = response.cookies[COOKIE_NAME]
    key = f"{storage.prefix}:admin:session:{hashlib.sha256(token.encode()).hexdigest()}"
    await storage.client.pexpire(key, 1)
    await asyncio.sleep(0.02)
    assert (await admin_client.get("/admin/api/v1/auth/session")).status_code == 401


async def test_origin_check_covers_login_and_logout(admin_client):
    assert (await login(admin_client, headers={"Origin": "https://untrusted.example"})).status_code == 403
    assert (await login(admin_client)).status_code == 200
    response = await admin_client.post("/admin/api/v1/auth/logout", headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 403
    assert (await admin_client.get("/admin/api/v1/auth/session")).status_code == 200


async def test_no_configured_password_fails_closed(admin_app, admin_client, admin_settings, storage):
    admin_settings.admin_password = None
    admin_app.state.services.admin_auth = AdminAuth(storage.client, storage.prefix, admin_settings)
    assert (await login(admin_client)).status_code == 503
    assert (await admin_client.get("/admin/api/v1/games")).status_code == 401


async def test_cookie_secure_is_configurable(admin_app, admin_client, admin_settings, storage):
    admin_settings.admin_cookie_secure = True
    admin_app.state.services.admin_auth = AdminAuth(storage.client, storage.prefix, admin_settings)
    response = await login(admin_client)
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


async def test_observer_shows_truth_without_inventing_death_author(authorized_client, admin_seed):
    game, _ = admin_seed
    response = await authorized_client.get(f"/admin/api/v1/games/{game.id}/state")
    assert response.status_code == 200
    state = response.json()
    assert state["werewolf_id"] == "bentinho"
    assert state["known_deaths"] == [{"victim_id": "bras_cubas", "victim_name": "Brás Cubas",
                                       "killer_id": None, "killer_name": None,
                                       "attribution": "unknown", "source": "scenario"}]
    assert state["player"]["location_id"] == "praca_verde"
    assert len(state["characters"]) == 3
    assert {character['character_id']: character['grammatical_gender'] for character in state['characters']} == {
        'bentinho': 'masculine', 'capitu': 'feminine', 'escobar': 'masculine'}
    assert all("werewolf_objective" not in character for character in state["characters"])
    assert (await authorized_client.get("/admin/api/v1/health")).json() == {"redis": "ok"}


async def test_indexes_pagination_and_empty_graph(authorized_client, admin_seed):
    game, conversation = admin_seed
    page = (await authorized_client.get("/admin/api/v1/games?limit=1")).json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == str(game.id)
    assert (await authorized_client.get("/admin/api/v1/games?offset=1")).json()["items"] == []
    convos = (await authorized_client.get(f"/admin/api/v1/games/{game.id}/conversations")).json()
    assert convos["items"][0]["id"] == str(conversation.id)
    graph = (await authorized_client.get(f"/admin/api/v1/games/{game.id}/interactions")).json()
    assert graph["edges"] == []
    assert {node["id"] for node in graph["nodes"]} == {"player", "capitu", "bentinho", "escobar"}


async def test_transcripts_beyond_200_and_real_graph_counts(authorized_client, admin_seed, storage, message_factory):
    game, conversation = admin_seed
    messages = tuple(message_factory(f"Fala {i}", "player" if i % 2 == 0 else "bentinho") for i in range(220))
    await storage.memory.append_messages(game.id, conversation.id, messages)
    url = f"/admin/api/v1/games/{game.id}/conversations/{conversation.id}/messages"
    first = (await authorized_client.get(f"{url}?limit=200")).json()
    second = (await authorized_client.get(f"{url}?offset=200&limit=200")).json()
    assert first["total"] == second["total"] == 220
    assert len(first["items"]) == 200 and len(second["items"]) == 20
    assert second["items"][-1]["content"] == "Fala 219"
    graph = (await authorized_client.get(f"/admin/api/v1/games/{game.id}/interactions")).json()
    assert graph["edges"][0]["message_count"] == 220
    assert graph["edges"][0]["conversation_id"] == str(conversation.id)


async def test_claimed_murder_does_not_change_death_truth(authorized_client, admin_seed, storage, message_factory):
    game, conversation = admin_seed
    await storage.memory.append_messages(game.id, conversation.id, (message_factory("Eu matei Brás Cubas", "bentinho"),))
    state = (await authorized_client.get(f"/admin/api/v1/games/{game.id}/state")).json()
    assert state["known_deaths"][0]["killer_id"] is None


async def test_rules_event_can_carry_real_author_but_narrative_claim_cannot(authorized_client, admin_seed, storage):
    game, _ = admin_seed
    key = f"{storage.prefix}:game:{{{game.id}}}:events"
    event = {"id": "rules-death", "type": "character.killed", "source": "rules",
             "occurred_at": datetime.now(UTC).isoformat(),
             "data": {"victim_id": "capitu", "killer_id": "bentinho"}}
    await storage.client.rpush(key, json.dumps(event))
    state = (await authorized_client.get(f"/admin/api/v1/games/{game.id}/state")).json()
    capitu = next(death for death in state["known_deaths"] if death["victim_id"] == "capitu")
    assert capitu["killer_id"] == "bentinho" and capitu["attribution"] == "known"


async def test_missing_and_invalid_pages(authorized_client):
    assert (await authorized_client.get(f"/admin/api/v1/games/{uuid4()}/state")).status_code == 404
    assert (await authorized_client.get("/admin/api/v1/games?limit=201")).status_code == 422
    assert (await authorized_client.get("/admin/api/v1/games?offset=-1")).status_code == 422


async def test_corrupt_event_is_sanitized(authorized_client, admin_seed, storage):
    game, _ = admin_seed
    await storage.client.rpush(f"{storage.prefix}:game:{{{game.id}}}:events", "private-corrupt-payload")
    response = await authorized_client.get(f"/admin/api/v1/games/{game.id}/events")
    assert response.status_code == 503
    assert "private-corrupt-payload" not in response.text
