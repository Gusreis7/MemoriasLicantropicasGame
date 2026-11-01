from uuid import UUID, uuid4

import pytest
from redis.exceptions import ConnectionError

pytestmark = pytest.mark.anyio


async def test_health_and_documentation(api_client):
    assert (await api_client.get("/health")).json() == {"status": "ok"}
    assert (await api_client.get("/")).json()["docs"] == "/docs"
    assert "/api/v1/games" in (await api_client.get("/openapi.json")).json()["paths"]
    assert (await api_client.get("/docs")).status_code == 200


async def test_catalog_is_public_and_has_seven_suspects(api_client):
    response = await api_client.get("/api/v1/characters")
    assert response.status_code == 200
    characters = response.json()
    assert len(characters) == 7
    assert len({character["id"] for character in characters}) == 7
    for character in characters:
        assert set(character) == {"id", "name", "bio"}
    assert "separar" not in (await api_client.get("/api/v1/characters/capitu")).json()["bio"]
    assert (await api_client.get("/api/v1/characters/desconhecido")).status_code == 404


@pytest.mark.parametrize("body", [None, {}])
async def test_create_game_persists_secret_and_returns_public_state(api_client, storage, body):
    response = await api_client.post("/api/v1/games", json=body)
    assert response.status_code == 201
    public = response.json()
    stored = await storage.games.get(UUID(public["id"]))
    assert stored is not None
    assert sum(character.role == "werewolf" for character in stored.characters) == 1
    assert len(public["characters"]) == 7
    assert public["status"] == "active"
    for state in public["characters"]:
        assert set(state) == {"character", "alive"}
        assert set(state["character"]) == {"id", "name", "bio"}
    assert (await api_client.get(f'/api/v1/games/{public["id"]}')).json() == public


@pytest.mark.parametrize("body", [{"seed": 1}, {"werewolf_id": "capitu"}, {"role": "civil"}])
async def test_client_cannot_control_draw(api_client, storage, body):
    assert (await api_client.post("/api/v1/games", json=body)).status_code == 422
    assert [key async for key in storage.client.scan_iter(match=f"{storage.prefix}:*")] == []


async def test_missing_and_invalid_game_ids(api_client):
    assert (await api_client.get(f"/api/v1/games/{uuid4()}")).status_code == 404
    assert (await api_client.get("/api/v1/games/invalid")).status_code == 422


async def test_storage_failure_is_503_without_internal_details(api_client, storage, monkeypatch):
    def fail(*args, **kwargs):
        raise ConnectionError("redis://private:password@internal:6379")
    monkeypatch.setattr(storage.client, "pipeline", fail)
    response = await api_client.post("/api/v1/games", json={})
    assert response.status_code == 503
    assert response.json() == {"detail": "Persistência temporariamente indisponível."}


async def test_separate_games_keep_their_draw(api_client, storage):
    first = (await api_client.post("/api/v1/games")).json()
    second = (await api_client.post("/api/v1/games")).json()
    assert first["id"] != second["id"]
    original = await storage.games.get(UUID(first["id"]))
    await api_client.get(f'/api/v1/games/{first["id"]}')
    assert await storage.games.get(UUID(first["id"])) == original
