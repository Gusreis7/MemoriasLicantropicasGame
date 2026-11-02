"""Fluxo REST composto: tempo, autorização, prova e confirmação noturna sem AWS."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from memorias_licantropicas.contracts.model import GameCharacter, GameState
from memorias_licantropicas.modules.investigation.catalog import INVENTORIES
from memorias_licantropicas.modules.world.repository import RedisWorldRepository

pytestmark = pytest.mark.anyio


async def seed_case(api_client, storage, catalog, wolf="capitu"):
    now = datetime.now(UTC)
    game = GameState(id=uuid4(), created_at=now, content_version=catalog.content_version,
                     characters=tuple(GameCharacter(character_id=profile.id,
                        role="werewolf" if profile.id == wolf else "civil") for profile in await catalog.list()))
    assert await storage.games.create(game)
    clock = [now]
    services = api_client._transport.app.state.services
    services.turns._clock = lambda: clock[0]
    base = f"/api/v1/games/{game.id}"
    case = (await api_client.get(f"{base}/investigation")).json()
    return game, clock, base, case


async def place(storage, game_id, location="praca_verde", x=600, npc_id=None):
    repository = RedisWorldRepository(storage.client, storage.prefix)
    world = await repository.get(game_id)
    if npc_id:
        npc = next(npc for npc in world.npcs if npc.npc_id == npc_id)
        location, x = npc.location_id, npc.x
    updated = world.model_copy(update={"revision": world.revision + 1,
        "player": world.player.model_copy(update={"location_id": location, "x": x, "direction": "idle"})})
    assert await repository.save(updated, expected_revision=world.revision)


async def test_clock_blocks_every_mutation_at_night_and_publishes_actual_death(api_client, storage, catalog):
    game, clock, base, case = await seed_case(api_client, storage, catalog)
    assert case["seconds_remaining"] == 300 and case["journal"][0]["title"] == "O Clarim do Rio"
    assert all(secret not in json.dumps(case) for secret in ("killer_id", "deposited_by", "truthful", "werewolf_id"))
    crime = case["crimes"][0]
    assert (await api_client.post(f"{base}/crime-scenes/{crime['id']}/search", json={})).status_code == 403
    await place(storage, game.id)
    case = (await api_client.post(f"{base}/crime-scenes/{crime['id']}/search", json={})).json()
    evidence_id = case["inventory"][0]["id"]
    await place(storage, game.id, npc_id="capitu")
    conversation = (await api_client.post(f"{base}/approaches", json={"npc_id": "capitu"})).json()
    clock[0] += timedelta(seconds=300)
    case = (await api_client.get(f"{base}/investigation")).json()
    assert case["phase"] == "night" and case["seconds_remaining"] == 8
    world = (await api_client.get(f"{base}/world")).json()
    commands = (
        ("movement", {"direction": "right", "seq": world["player"]["movement_seq"] + 1,
                      "location_id": world["location"]["id"], "revision": world["revision"]}),
        ("travel", {"target_location_id": "casa_verde", "revision": world["revision"]}),
        ("approaches", {"npc_id": "capitu"}),
        (f"conversations/{conversation['id']}/messages", {"content": "Olá"}),
        (f"crime-scenes/{crime['id']}/search", {}),
        (f"evidence/{evidence_id}/present", {"npc_id": "capitu"}),
        ("accusations", {"suspect_id": "capitu", "evidence_ids": [], "testimony_ids": []}),
    )
    for path, body in commands:
        assert (await api_client.post(f"{base}/{path}", json=body)).status_code == 409, path
    clock[0] += timedelta(seconds=8)
    dawn = (await api_client.get(f"{base}/investigation")).json()
    assert dawn["phase"] == "day" and dawn["day"] == 2
    assert dawn["journal"][-1]["victim_id"] == "escobar"
    assert len(dawn["crimes"]) == 2 and len(dawn["inventory"]) == 1
    public_game = (await api_client.get(base)).json()
    assert sum(npc["alive"] for npc in public_game["characters"]) == 6
    morning_world = (await api_client.get(f"{base}/world")).json()
    assert morning_world["player"]["location_id"] == "praca_verde" and morning_world["player"]["x"] == 160
    events = await storage.client.lrange(f"{storage.prefix}:game:{{{game.id}}}:events", 0, -1)
    assert sum(json.loads(event)["type"] == "character.killed" for event in events) == 1
    await api_client.get(f"{base}/investigation")
    assert await storage.client.llen(f"{storage.prefix}:game:{{{game.id}}}:events") == len(events)


@pytest.mark.parametrize("wolf", tuple(INVENTORIES))
async def test_collected_evidence_and_testimony_lead_to_night_confirmed_victory(api_client, storage, catalog, wolf):
    game, clock, base, case = await seed_case(api_client, storage, catalog, wolf)
    await place(storage, game.id)
    crime = case["crimes"][0]
    for _ in range(3):  # A terceira busca é idempotente.
        result = await api_client.post(f"{base}/crime-scenes/{crime['id']}/search", json={})
        assert result.status_code == 200
        case = result.json()
    assert len(case["inventory"]) == 2
    for npc in game.characters:
        if npc.character_id == wolf:
            continue
        await place(storage, game.id, npc_id=npc.character_id)
        for evidence in case["inventory"]:
            result = await api_client.post(f"{base}/evidence/{evidence['id']}/present", json={"npc_id": npc.character_id})
            assert result.status_code == 200
            case = result.json()
    linked = [statement["id"] for statement in case["testimonies"] if statement["claimed_owner_id"] == wolf]
    result = await api_client.post(f"{base}/accusations", json={"suspect_id": wolf,
        "evidence_ids": [item["id"] for item in case["inventory"]], "testimony_ids": linked})
    assert result.status_code == 200
    detained = result.json()
    assert detained["accusations"][-1]["accepted"] and detained["detained_npc_id"] == wolf
    assert detained["status"] == "active" and detained["ending"] is None
    assert (await api_client.post(f"{base}/accusations", json={"suspect_id": wolf})).status_code == 409
    assert detained["phase"] == "night" and detained["seconds_remaining"] == 8
    clock[0] += timedelta(seconds=7)
    waiting = (await api_client.get(f"{base}/investigation")).json()
    assert waiting["phase"] == "night" and waiting["status"] == "active"
    assert waiting["seconds_remaining"] == 1 and waiting["ending"] is None
    clock[0] += timedelta(seconds=1)
    finished = (await api_client.get(f"{base}/investigation")).json()
    assert finished["status"] == "won" and finished["phase"] == "finished"
    assert finished["ending"]["werewolf_id"] == wolf
    assert finished["journal"][-1]["detention_outcome"] == "transformed"
    assert finished["journal"][-1]["victim_id"] is None
    assert (await api_client.get(base)).json()["status"] == "won"
    after_expulsion = await RedisWorldRepository(storage.client, storage.prefix).get(game.id)
    assert wolf not in {npc.npc_id for npc in after_expulsion.npcs}
    assert all(member.alive for member in (await storage.games.get(game.id)).characters)


async def test_inference_crossing_deadline_cannot_append_a_dialogue(api_client, storage, catalog, llm, monkeypatch):
    game, clock, base, case = await seed_case(api_client, storage, catalog)
    await place(storage, game.id, npc_id="capitu")
    conversation = (await api_client.post(f"{base}/approaches", json={"npc_id": "capitu"})).json()
    complete = llm.complete
    async def late(messages):
        clock[0] += timedelta(seconds=300)
        return await complete(messages)
    monkeypatch.setattr(llm, "complete", late)
    result = await api_client.post(f"{base}/conversations/{conversation['id']}/messages", json={"content": "O que viu hoje?"})
    assert result.status_code == 409
    history = await api_client.get(f"{base}/conversations/{conversation['id']}/messages")
    assert history.json()["messages"] == []
    assert (await api_client.get(f"{base}/investigation")).json()["phase"] == "night"
