import asyncio
import json
from uuid import UUID, uuid4

import pytest
import httpx

from src.contracts.errors import (
    LLM_PUBLIC_DETAILS,
    LLMUnavailableError,
    StorageUnavailableError,
)
from src.contracts.model import Conversation, LLMResponse
from src.infrastructure.llm.bedrock_mantle import BedrockMantleClient

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
    "npc_id",
    ["bentinho", "capitu", "escobar", "rubiao", "virgilia", "florenca", "bacamarte"],
)
async def test_player_can_talk_to_each_persona(api_client, storage, llm, npc_id):
    game, conversation = await open_conversation(api_client, storage, npc_id)
    url = f"/api/v1/games/{game['id']}/conversations/{conversation['id']}"
    assert (await api_client.get(url)).json() == conversation
    assert (await api_client.get(f"{url}/messages")).json()["messages"] == []
    response = await api_client.post(
        f"{url}/messages", json={"content": "O que sabe sobre Brás Cubas?"}
    )
    assert response.status_code == 200
    assert set(response.json()) == {"conversation_id", "message"}
    assert response.json()["message"]["speaker"] == "npc"
    assert set(response.json()["message"]) == {
        "id",
        "speaker",
        "content",
        "created_at",
        "useful",
    }
    history = (await api_client.get(f"{url}/messages")).json()["messages"]
    assert [message["speaker"] for message in history] == ["player", "npc"]
    await api_client.post(f"{url}/messages", json={"content": "Tem certeza?"})
    assert "Brás Cubas" in llm.calls[-1][1].content
    assert len((await api_client.get(f"{url}/messages")).json()["messages"]) == 4


async def test_incompatible_saved_game_rejects_reads_and_chat_without_llm(api_client, storage, llm):
    game = (await api_client.post("/api/v1/games")).json()
    game_id = UUID(game["id"])
    state = await storage.games.get(game_id)
    await storage.client.set(f"{storage.prefix}:game:{{{game_id}}}:state",
        state.model_copy(update={"content_version": "2"}).model_dump_json())
    assert (await api_client.get(f"/api/v1/games/{game_id}")).status_code == 409
    response = await api_client.post(f"/api/v1/games/{game_id}/conversations",
        json={"npc_id": "capitu"})
    assert response.status_code == 409
    assert llm.calls == []
    assert (await storage.games.get(game_id)).content_version == "2"


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


async def test_failure_keeps_history_empty_and_releases_gate(api_client, storage, llm):
    game, conversation = await open_conversation(api_client, storage)
    url = f"/api/v1/games/{game['id']}/conversations/{conversation['id']}/messages"
    llm.error = LLMUnavailableError("private-provider-detail")
    response = await api_client.post(url, json={"content": "Olá"})
    assert response.status_code == 503
    assert "private-provider-detail" not in response.text
    assert (await api_client.get(url)).json()["messages"] == []
    llm.error = None
    assert (await api_client.post(url, json={"content": "Olá"})).status_code == 200


@pytest.mark.parametrize("code", [*LLM_PUBLIC_DETAILS, "unknown-private-provider-code"])
async def test_http_dialogue_error_exposes_only_whitelisted_diagnostic(
    api_client, storage, llm, caplog, code
):
    game, conversation = await open_conversation(api_client, storage)
    url = f"/api/v1/games/{game['id']}/conversations/{conversation['id']}/messages"
    raw_private = "PRIVATE_PROVIDER_BODY PRIVATE_API_KEY PRIVATE_PROFILE PRIVATE_PROMPT"
    llm.error = LLMUnavailableError(raw_private, code=code)
    expected_code = code if code in LLM_PUBLIC_DETAILS else "llm_unavailable"
    response = await api_client.post(url, json={"content": "O que ouviu hoje?"})
    diagnostic_logs = [
        record.getMessage()
        for record in caplog.records
        if record.name == "src.main"
    ]
    if expected_code in {"llm_invalid_response", "llm_response_truncated"}:
        from src.modules.agents.workflow import TECHNICAL_FALLBACK

        assert response.status_code == 200
        assert response.json()["message"]["content"] == TECHNICAL_FALLBACK
        saved = await storage.memory.list_messages(
            UUID(game["id"]), UUID(conversation["id"]), "player"
        )
        assert (
            len(saved) == 2
            and not saved[-1].narrative_authorized
            and not saved[-1].useful
        )
        assert diagnostic_logs == []
    else:
        assert response.status_code == 503
        assert response.json() == {
            "detail": LLM_PUBLIC_DETAILS[expected_code],
            "code": expected_code,
        }
        assert (await api_client.get(url)).json()["messages"] == []
        assert diagnostic_logs == [f"dialogue_unavailable code={expected_code}"]
    assert all(
        secret not in response.text + caplog.text for secret in raw_private.split()
    )
    if code not in LLM_PUBLIC_DETAILS:
        assert code not in response.text + caplog.text


async def test_storage_503_keeps_its_original_public_contract(api_client, storage, llm):
    game, conversation = await open_conversation(api_client, storage)
    url = f"/api/v1/games/{game['id']}/conversations/{conversation['id']}/messages"
    llm.error = StorageUnavailableError("private-redis-diagnostic")
    response = await api_client.post(url, json={"content": "Olá"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Persistência temporariamente indisponível."}
    assert "private-redis-diagnostic" not in response.text


@pytest.mark.parametrize(
    "with_profile,code",
    [
        (False, "llm_credentials_missing"),
        (True, "llm_credentials_unavailable"),
    ],
)
async def test_missing_or_expired_credentials_do_not_send_http_or_save_half_dialogue(
    api_client,
    storage,
    llm,
    monkeypatch,
    caplog,
    with_profile,
    code,
):
    import src.infrastructure.llm.aws_credentials as credentials_module

    game, conversation = await open_conversation(api_client, storage)
    url = f"/api/v1/games/{game['id']}/conversations/{conversation['id']}/messages"
    raw_private = "PRIVATE_TOKEN_CACHE PRIVATE_AWS_PROFILE PRIVATE_PROMPT"

    def fail_credentials(**kwargs):
        raise RuntimeError(raw_private)

    def forbidden(request):
        pytest.fail("Credenciais indisponíveis não podem disparar HTTP ao provedor")

    monkeypatch.setattr(credentials_module, "provide_token", fail_credentials)
    provider = (
        credentials_module.ProfileTokenProvider("PRIVATE_AWS_PROFILE", "us-east-1")
        if with_profile
        else None
    )
    client = BedrockMantleClient(
        base_url="https://example.invalid/v1",
        api_key=None,
        model="test-model",
        timeout_seconds=1,
        max_tokens=64,
        token_provider=provider,
    )
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://example.invalid/v1/", transport=httpx.MockTransport(forbidden)
    )
    original_complete = llm.complete
    monkeypatch.setattr(llm, "complete", client.complete)
    try:
        response = await api_client.post(
            url, json={"content": "Minha pergunta privada sobre a cidade."}
        )
        assert response.status_code == 503
        assert response.json() == {"code": code, "detail": LLM_PUBLIC_DETAILS[code]}
        assert (await api_client.get(url)).json()["messages"] == []
        outbox = f"{storage.prefix}:game:{{{game['id']}}}:social:exchanges"
        assert await storage.client.llen(outbox) == 0
        assert all(
            secret not in response.text + caplog.text for secret in raw_private.split()
        )
        monkeypatch.setattr(llm, "complete", original_complete)
        assert (
            await api_client.post(url, json={"content": "Podemos tentar outra vez?"})
        ).status_code == 200
        assert len((await api_client.get(url)).json()["messages"]) == 2
    finally:
        await client.aclose()


async def test_invalid_persona_output_returns_safe_specific_diagnostic(
    api_client, storage, llm, monkeypatch, caplog
):
    game, conversation = await open_conversation(api_client, storage)
    url = f"/api/v1/games/{game['id']}/conversations/{conversation['id']}/messages"

    async def invalid(messages, *, tools=(), tool_choice=None):
        return LLMResponse(
            content="<think>PRIVATE_PROVIDER_REASONING</think>Olá", model="stub"
        )

    monkeypatch.setattr(llm, "complete", invalid)
    response = await api_client.post(url, json={"content": "Olá"})
    from src.modules.agents.workflow import TECHNICAL_FALLBACK

    assert response.status_code == 200
    assert response.json()["message"]["content"] == TECHNICAL_FALLBACK
    assert "PRIVATE_PROVIDER_REASONING" not in response.text + caplog.text
    history = (await api_client.get(url)).json()["messages"]
    assert len(history) == 2 and history[-1]["content"] == TECHNICAL_FALLBACK
    saved = await storage.memory.list_messages(
        UUID(game["id"]), UUID(conversation["id"]), "player"
    )
    assert not saved[-1].narrative_authorized and not saved[-1].useful


async def test_concurrent_messages_are_rejected_until_first_finishes(
    api_client, storage, llm, monkeypatch
):
    game, conversation = await open_conversation(api_client, storage)
    url = f"/api/v1/games/{game['id']}/conversations/{conversation['id']}/messages"
    started, resume = asyncio.Event(), asyncio.Event()
    original = llm.complete

    async def delayed(messages, *, tools=(), tool_choice=None):
        started.set()
        await resume.wait()
        return await original(messages, tools=tools, tool_choice=tool_choice)

    monkeypatch.setattr(llm, "complete", delayed)
    task = asyncio.create_task(
        api_client.post(url, json={"content": "Primeira pergunta"})
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=3)
        assert (
            await api_client.post(url, json={"content": "Outra pergunta"})
        ).status_code == 409
    finally:
        resume.set()
        response = await task
    assert response.status_code == 200
    assert len((await api_client.get(url)).json()["messages"]) == 2


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


async def test_strategy_projection_excludes_werewolf_tactic_for_civil(
    api_client, storage, llm, catalog
):
    game, conversation = await open_conversation(api_client, storage)
    stored = await storage.games.get(UUID(game["id"]))
    capitu = next(npc for npc in stored.characters if npc.character_id == "capitu")
    await api_client.post(
        f"/api/v1/games/{game['id']}/conversations/{conversation['id']}/messages",
        json={"content": "Você coopera?"},
    )
    context = json.loads(llm.calls[0][0].content.split("Ficha privada:\n", 1)[1])
    strategy = (await catalog.get("capitu")).dialogue_strategy
    expected = (
        strategy.werewolf_tactic if capitu.role == "werewolf" else strategy.civil_tactic
    )
    assert context["estrategia_de_conversa"]["tatica_ativa"] == expected


async def test_history_limit_is_validated(api_client, storage):
    game, conversation = await open_conversation(api_client, storage)
    url = f"/api/v1/games/{game['id']}/conversations/{conversation['id']}/messages"
    for limit in (0, 201):
        assert (await api_client.get(url, params={"limit": limit})).status_code == 422
