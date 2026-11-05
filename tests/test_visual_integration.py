import asyncio
import json
from uuid import UUID

import pytest

from memorias_licantropicas.modules.world.model import WorldState

pytestmark = pytest.mark.anyio


async def place_at(storage, game_id, npc_id):
    key = f"{storage.prefix}:game:{{{game_id}}}:world"
    world = WorldState.model_validate_json(await storage.client.get(key))
    npc = next(npc for npc in world.npcs if npc.npc_id == npc_id)
    player = world.player.model_copy(
        update={"location_id": npc.location_id, "x": npc.x, "direction": "idle"}
    )
    await storage.client.set(
        key, world.model_copy(update={"player": player}).model_dump_json()
    )


async def test_game_bootstrap_is_visible_to_admin_without_leaking_public_state(
    api_client, storage
):
    game = (await api_client.post("/api/v1/games", json={})).json()
    game_id = game["id"]
    world = (await api_client.get(f"/api/v1/games/{game_id}/world")).json()
    assert world["player"]["location_id"] == "praca_verde"
    assert [npc["npc_id"] for npc in world["visible_npcs"]] == ["rubiao"]
    assert "werewolf" not in json.dumps(world)
    assert (await api_client.get("/admin/api/v1/games")).status_code == 401
    assert (
        await api_client.post(
            "/admin/api/v1/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
    ).status_code == 200
    records = (await api_client.get("/admin/api/v1/games")).json()
    assert records["total"] == 1
    assert records["items"][0]["id"] == game_id
    state = (await api_client.get(f"/admin/api/v1/games/{game_id}/state")).json()
    persisted = await storage.games.get(UUID(game_id))
    assert state["werewolf_id"] == next(
        n.character_id for n in persisted.characters if n.role == "werewolf"
    )
    assert state["known_deaths"][0]["killer_id"] is None
    events = (await api_client.get(f"/admin/api/v1/games/{game_id}/events")).json()[
        "items"
    ]
    assert {event["type"] for event in events} == {
        "game.created",
        "world.initialized",
        "story.initial_death",
    }


async def test_revisit_reuses_thread_and_duplicate_messages_do_not_duplicate_events(
    api_client, storage
):
    game = (await api_client.post("/api/v1/games")).json()
    game_id = UUID(game["id"])
    base = f"/api/v1/games/{game_id}"
    await place_at(storage, game_id, "capitu")
    conversation = (
        await api_client.post(f"{base}/approaches", json={"npc_id": "capitu"})
    ).json()
    cid = UUID(conversation["id"])
    url = f"{base}/conversations/{cid}/messages"
    assert (
        await api_client.post(url, json={"content": "Boa tarde"})
    ).status_code == 200
    messages = await storage.memory.list_messages(game_id, cid, "player")
    await storage.memory.append_messages(game_id, cid, messages)
    snapshot = (await api_client.get(f"{base}/world")).json()
    assert (
        await api_client.post(
            f"{base}/travel",
            json={
                "target_location_id": "praca_verde",
                "revision": snapshot["revision"],
            },
        )
    ).status_code == 200
    assert (
        await api_client.post(url, json={"content": "Não estou mais perto"})
    ).status_code == 403
    assert len((await api_client.get(url)).json()["messages"]) == 2
    await place_at(storage, game_id, "capitu")
    revisited = (
        await api_client.post(f"{base}/approaches", json={"npc_id": "capitu"})
    ).json()
    assert revisited["id"] == str(cid)
    raw = await storage.client.lrange(
        f"{storage.prefix}:game:{{{game_id}}}:events", 0, -1
    )
    types = [json.loads(event)["type"] for event in raw]
    assert types.count("conversation.created") == 1
    assert types.count("conversation.exchange_committed") == 1


async def test_player_cannot_travel_during_pending_response(
    api_client, storage, llm, monkeypatch
):
    game_id = (await api_client.post("/api/v1/games")).json()["id"]
    base = f"/api/v1/games/{game_id}"
    await place_at(storage, game_id, "capitu")
    cid = (
        await api_client.post(f"{base}/approaches", json={"npc_id": "capitu"})
    ).json()["id"]
    started, release = asyncio.Event(), asyncio.Event()
    complete = llm.complete

    async def pending(messages, *, tools=(), tool_choice=None):
        started.set()
        await release.wait()
        return await complete(messages, tools=tools, tool_choice=tool_choice)

    monkeypatch.setattr(llm, "complete", pending)
    task = asyncio.create_task(
        api_client.post(f"{base}/conversations/{cid}/messages", json={"content": "Olá"})
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=3)
        snapshot = (await api_client.get(f"{base}/world")).json()
        assert (
            await api_client.post(
                f"{base}/travel",
                json={
                    "target_location_id": "casa_verde",
                    "revision": snapshot["revision"],
                },
            )
        ).status_code == 409
    finally:
        release.set()
        response = await task
    assert response.status_code == 200
