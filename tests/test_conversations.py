from uuid import UUID, uuid4

import pytest

from src.contracts.model import Conversation

pytestmark = pytest.mark.anyio


async def open_conversation(client, storage, npc_id="capitu"):
    game = (await client.post("/api/v1/games")).json()
    world_key = f"{storage.prefix}:game:{{{game['id']}}}:world"
    from src.modules.world.model import WorldState

    world = WorldState.model_validate_json(await storage.client.get(world_key))
    target = next(npc for npc in world.npcs if npc.npc_id == npc_id)
    world = world.model_copy(
        update={
            "player": world.player.model_copy(
                update={"location_id": target.location_id, "x": target.x}
            )
        }
    )
    await storage.client.set(world_key, world.model_dump_json())
    response = await client.post(
        f"/api/v1/games/{game['id']}/conversations", json={"npc_id": npc_id}
    )
    assert response.status_code == 201
    return game, response.json()


@pytest.mark.parametrize(
    "body",
    [
        {"content": ""},
        {"content": "   "},
        {"content": "x" * 8001},
        {"content": "Bom dia", "speaker_id": "escobar"},
        {"content": "Bom dia", "npc_id": "escobar"},
    ],
)
async def test_bad_input_or_spoofing_never_calls_llm(api_client, storage, llm, body):
    game, conversation = await open_conversation(api_client, storage)
    url = f"/api/v1/games/{game['id']}/conversations/{conversation['id']}/messages"
    assert (await api_client.post(url, json=body)).status_code == 422
    assert llm.calls == []


async def test_cross_game_and_npc_private_conversations_are_inaccessible(
    api_client, storage
):
    game, public = await open_conversation(api_client, storage)
    game_id = UUID(game["id"])
    other = (await api_client.post("/api/v1/games")).json()
    assert (
        await api_client.get(
            f"/api/v1/games/{other['id']}/conversations/{public['id']}/messages"
        )
    ).status_code == 404
    private = Conversation(
        id=uuid4(),
        game_id=game_id,
        participant_ids=("capitu", "bentinho"),
        created_at=(await storage.games.get(game_id)).created_at,
    )
    await storage.memory.create_conversation(private)
    url = f"/api/v1/games/{game_id}/conversations/{private.id}"
    assert (await api_client.get(f"{url}/messages")).status_code == 403
    assert (
        await api_client.post(f"{url}/messages", json={"content": "Olá"})
    ).status_code == 403


async def test_missing_dead_or_outdated_targets_are_rejected(api_client, storage, game):
    assert (
        await api_client.post(
            f"/api/v1/games/{uuid4()}/conversations", json={"npc_id": "capitu"}
        )
    ).status_code == 404
    dead = game.model_copy(
        update={
            "characters": tuple(
                npc.model_copy(update={"alive": False})
                if npc.character_id == "capitu"
                else npc
                for npc in game.characters
            )
        }
    )
    await storage.games.create(dead)
    base = f"/api/v1/games/{game.id}/conversations"
    assert (await api_client.post(base, json={"npc_id": "capitu"})).status_code == 403
    assert (await api_client.post(base, json={"npc_id": "player"})).status_code == 404
    old = game.model_copy(update={"id": uuid4(), "content_version": "1"})
    await storage.games.create(old)
    assert (
        await api_client.post(
            f"/api/v1/games/{old.id}/conversations", json={"npc_id": "capitu"}
        )
    ).status_code == 409
