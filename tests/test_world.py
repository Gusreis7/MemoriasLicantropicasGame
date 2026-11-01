import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from memorias_licantropicas.contracts.errors import (
    AccessDeniedError, ConflictError, LLMUnavailableError, NotFoundError, StorageUnavailableError,
)
from memorias_licantropicas.contracts.model import GameCharacter, GameState
from memorias_licantropicas.modules.world.catalog import LOCATIONS, make_initial_world
from memorias_licantropicas.modules.world.gate import RedisPlayerGate
from memorias_licantropicas.modules.world.repository import RedisWorldRepository
from memorias_licantropicas.modules.world.router import get_world_service, router
from memorias_licantropicas.modules.world.schema import MoveRequest, TravelRequest
from memorias_licantropicas.modules.world.service import WorldService

pytestmark = pytest.mark.anyio


@pytest.fixture
async def world_context(storage, catalog):
    game_id = uuid4()
    profiles = await catalog.list()
    game = GameState(id=game_id, created_at=datetime.now(UTC), content_version=catalog.content_version,
                     characters=tuple(GameCharacter(character_id=profile.id,
                                     role="werewolf" if profile.id == "capitu" else "civil")
                                      for profile in profiles))
    games = AsyncMock()
    games.get.return_value = game
    repository = RedisWorldRepository(storage.client, storage.prefix)
    current = [datetime(2026, 11, 1, tzinfo=UTC)]
    initial = make_initial_world(game_id)
    initial = initial.model_copy(update={"player": initial.player.model_copy(update={"last_updated_at": current[0]})})
    await repository.create(initial)
    gate = RedisPlayerGate(storage.client, storage.prefix)
    service = WorldService(games, catalog, repository, gate, clock=lambda: current[0])
    return SimpleNamespace(game=game, games=games, repository=repository, gate=gate,
                           clock=current, initial=initial, service=service)


def command(snapshot, direction="right", seq=None):
    return MoveRequest(direction=direction, seq=seq or snapshot.player.movement_seq + 1,
                       location_id=snapshot.player.location_id, revision=snapshot.revision)


async def test_world_snapshot_has_only_current_npcs_and_public_fields(world_context):
    snapshot = await world_context.service.get(world_context.game.id)
    assert snapshot.location.id == "praca_verde"
    assert snapshot.player.x == 160
    assert [npc.npc_id for npc in snapshot.visible_npcs] == ["rubiao"]
    assert not snapshot.visible_npcs[0].can_approach
    assert set(snapshot.travel_targets) == {location.id for location in LOCATIONS if location.id != "praca_verde"}
    payload = snapshot.model_dump_json()
    assert "werewolf" not in payload and "role" not in payload and "objective" not in payload


async def test_bootstrap_is_insert_only_and_independent_of_roles(world_context):
    assert await world_context.repository.create(world_context.initial) is False
    assert make_initial_world(uuid4()).npcs == world_context.initial.npcs
    assert len({npc.npc_id for npc in world_context.initial.npcs}) == 7


async def test_server_time_and_previous_direction_determine_movement(world_context):
    service, clock, game_id = world_context.service, world_context.clock, world_context.game.id
    snapshot = await service.get(game_id)
    started = await service.move(game_id, command(snapshot))
    assert started.player.x == 160  # Enviar intenção não permite escolher coordenadas.
    clock[0] += timedelta(milliseconds=150)
    walked = await service.move(game_id, command(started))
    assert walked.player.x == 191.5
    clock[0] += timedelta(milliseconds=150)
    stopped = await service.move(game_id, command(walked, "idle"))
    assert stopped.player.x == 223
    clock[0] += timedelta(seconds=10)
    still = await service.move(game_id, command(stopped, "idle"))
    assert still.player.x == stopped.player.x


async def test_long_disconnect_and_negative_clock_are_bounded(world_context):
    context = world_context
    snapshot = await context.service.move(context.game.id, command(await context.service.get(context.game.id)))
    context.clock[0] += timedelta(hours=1)
    snapshot = await context.service.move(context.game.id, command(snapshot))
    assert snapshot.player.x == 244  # 210 px/s × no máximo 400 ms.
    context.clock[0] -= timedelta(seconds=1)
    snapshot = await context.service.move(context.game.id, command(snapshot))
    assert snapshot.player.x == 244


@pytest.mark.parametrize("direction,initial_x,expected", [("left", 33, 32), ("right", 1887, 1888)])
async def test_scene_boundaries(world_context, direction, initial_x, expected):
    context = world_context
    state = context.initial.model_copy(update={"revision": 1, "player": context.initial.player.model_copy(
        update={"x": initial_x, "direction": direction})})
    assert await context.repository.save(state, expected_revision=0)
    context.clock[0] += timedelta(milliseconds=400)
    result = await context.service.move(context.game.id, command(await context.service.get(context.game.id), direction))
    assert result.player.x == expected


async def test_stale_sequence_location_and_revision_are_rejected(world_context):
    context = world_context
    first = await context.service.move(context.game.id, command(await context.service.get(context.game.id)))
    with pytest.raises(ConflictError):
        await context.service.move(context.game.id, command(first, seq=1))
    with pytest.raises(ConflictError):
        await context.service.move(context.game.id, command(first).model_copy(update={"location_id": "casa_verde"}))
    with pytest.raises(ConflictError):
        await context.service.move(context.game.id, command(first).model_copy(update={"revision": 0}))
    assert (await context.service.get(context.game.id)).revision == 1


async def test_travel_has_safe_spawn_and_atomic_real_event(world_context, storage):
    context = world_context
    snapshot = await context.service.travel(context.game.id, TravelRequest(target_location_id="cabana_capitu", revision=0))
    assert snapshot.player.x == 160
    assert snapshot.player.facing == "right"
    assert snapshot.location.id == "cabana_capitu"
    assert [npc.npc_id for npc in snapshot.visible_npcs] == ["capitu", "virgilia"]
    stored = await context.repository.get(context.game.id)
    assert stored.player.direction == "idle"
    records = await storage.client.lrange(f"{storage.prefix}:game:{{{context.game.id}}}:events", 0, -1)
    assert len(records) == 1
    event = json.loads(records[0])
    assert event["type"] == "player.travelled"
    assert event["data"]["from_location_id"] == "praca_verde"
    assert event["data"]["to_location_id"] == "cabana_capitu"
    with pytest.raises(ConflictError):
        await context.service.travel(context.game.id, TravelRequest(target_location_id="cafe_largo", revision=0))
    assert await storage.client.llen(f"{storage.prefix}:game:{{{context.game.id}}}:events") == 1


async def test_proximity_requires_same_location_alive_and_64_pixels(world_context):
    context = world_context
    with pytest.raises(AccessDeniedError):
        await context.service.assert_can_talk(context.game.id, "capitu")
    with pytest.raises(AccessDeniedError):
        await context.service.assert_can_talk(context.game.id, "rubiao")
    state = context.initial.model_copy(update={"revision": 1, "player": context.initial.player.model_copy(update={"x": 376})})
    await context.repository.save(state, expected_revision=0)
    await context.service.assert_can_talk(context.game.id, "rubiao")
    assert (await context.service.get(context.game.id)).visible_npcs[0].can_approach is True
    context.games.get.return_value = context.game.model_copy(update={"characters": tuple(
        npc.model_copy(update={"alive": False}) if npc.character_id == "rubiao" else npc
        for npc in context.game.characters)})
    with pytest.raises(AccessDeniedError):
        await context.service.assert_can_talk(context.game.id, "rubiao")
    assert (await context.service.get(context.game.id)).visible_npcs == ()


async def test_missing_and_old_games_do_not_create_or_reroll_world(world_context):
    context = world_context
    with pytest.raises(ConflictError):
        await context.service.get(uuid4())  # Mock game exists, but no world has been initialized.
    context.games.get.return_value = None
    with pytest.raises(NotFoundError):
        await context.service.get(context.game.id)
    context.games.get.return_value = context.game.model_copy(update={"content_version": "1"})
    with pytest.raises(ConflictError):
        await context.service.get(context.game.id)
    context.games.create.assert_not_awaited()


async def test_player_gate_blocks_world_actions_while_dialogue_holds_it(world_context):
    context = world_context
    async with context.gate.hold(context.game.id):
        with pytest.raises(ConflictError):
            await context.service.move(context.game.id, command(await context.service.get(context.game.id)))
        with pytest.raises(ConflictError):
            await context.service.travel(context.game.id, TravelRequest(target_location_id="cafe_largo", revision=0))
    assert (await context.service.get(context.game.id)).revision == 0


async def test_repository_cas_rejects_lost_updates_and_corruption(world_context, storage):
    context = world_context
    updated = context.initial.model_copy(update={"revision": 1})
    assert await context.repository.save(updated, expected_revision=0)
    assert not await context.repository.save(updated, expected_revision=0)
    await storage.client.set(f"{storage.prefix}:game:{{{context.game.id}}}:world", "invalid-json")
    with pytest.raises(StorageUnavailableError):
        await context.repository.get(context.game.id)


async def test_wrong_event_key_type_never_partially_travels(world_context, storage):
    context = world_context
    await storage.client.set(f"{storage.prefix}:game:{{{context.game.id}}}:events", "not-a-list")
    with pytest.raises(StorageUnavailableError):
        await context.service.travel(context.game.id, TravelRequest(target_location_id="cafe_largo", revision=0))
    assert await context.repository.get(context.game.id) == context.initial


async def test_gate_timeout_and_owner_safety(storage):
    game_id = uuid4()
    gate = RedisPlayerGate(storage.client, storage.prefix, timeout_seconds=0.01)
    with pytest.raises(LLMUnavailableError):
        async with gate.hold(game_id):
            await asyncio.sleep(1)
    key = f"{storage.prefix}:game:{{{game_id}}}:player:busy"
    assert await storage.client.get(key) is None
    async with gate.hold(game_id):
        await storage.client.set(key, "replacement-owner", ex=10)
    assert await storage.client.get(key) == "replacement-owner"


async def test_public_router_and_command_validation(world_context):
    app = FastAPI()
    app.include_router(router)

    async def service():
        return world_context.service

    app.dependency_overrides[get_world_service] = service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        locations = await client.get("/api/v1/world/locations")
        assert locations.status_code == 200
        assert len(locations.json()) == 5
        assert all(set(location) == {"id", "name", "width", "height", "ground_y", "background"}
                   for location in locations.json())
        base = f"/api/v1/games/{world_context.game.id}"
        assert (await client.get(f"{base}/world")).json()["player"]["location_id"] == "praca_verde"
        assert (await client.post(f"{base}/movement", json={"direction": "right", "seq": 1,
                "location_id": "praca_verde", "revision": 0, "x": 440})).status_code == 422
        assert (await client.post(f"{base}/travel", json={"target_location_id": "unknown", "revision": 0})).status_code == 422


@pytest.mark.parametrize("data", [
    {"direction": "up", "seq": 1, "location_id": "praca_verde", "revision": 0},
    {"direction": "left", "seq": True, "location_id": "praca_verde", "revision": 0},
    {"direction": "left", "seq": 0, "location_id": "praca_verde", "revision": 0},
])
async def test_move_schema_rejects_invalid_commands(data):
    with pytest.raises(ValidationError):
        MoveRequest.model_validate(data)
