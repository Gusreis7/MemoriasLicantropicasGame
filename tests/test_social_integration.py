"""Fronteiras entre transcrição, outbox, conhecimento e projeção pública."""

from uuid import uuid4
from dataclasses import replace

import pytest

from memorias_licantropicas.contracts.errors import StorageUnavailableError
from memorias_licantropicas.contracts.social import ExchangeRecord
from memorias_licantropicas.infrastructure.social_repository import RedisSocialRepository
from memorias_licantropicas.modules.social.views import SocialReadService

pytestmark = pytest.mark.anyio


async def test_exchange_outbox_is_atomic_idempotent_and_only_records_heard_pairs(
    storage, game, conversation, message_factory,
):
    incoming = message_factory("Virgília disse que Capitu esteve no cais.")
    outgoing = message_factory("Foi o senhor quem me contou isso.", "bentinho")
    pair = (incoming, outgoing)
    await storage.memory.append_messages(game.id, conversation.id, pair)
    await storage.memory.append_messages(game.id, conversation.id, pair)
    repository = RedisSocialRepository(storage.client, storage.prefix)
    records = await repository.exchanges(game.id, 0)
    assert records == (ExchangeRecord(conversation_id=conversation.id, npc_id="bentinho",
                                     day=1,
                                     incoming=incoming, outgoing=outgoing),)
    assert await storage.memory.list_messages(game.id, conversation.id, "player") == pair


async def test_wrong_outbox_type_does_not_commit_half_a_conversation(
    storage, game, conversation, message_factory,
):
    await storage.client.set(f"{storage.prefix}:game:{{{game.id}}}:social:exchanges", "broken")
    pair = (message_factory("O que sabe?"), message_factory("Nada vi.", "bentinho"))
    with pytest.raises(StorageUnavailableError):
        await storage.memory.append_messages(game.id, conversation.id, pair)
    assert await storage.memory.list_messages(game.id, conversation.id, "player") == ()


async def test_public_notebook_contains_only_utterances_actually_heard_by_player(
    storage, game, conversation, catalog, message_factory,
):
    from memorias_licantropicas.contracts.model import Conversation
    await storage.memory.append_messages(game.id, conversation.id, (
        message_factory("O que Capitu lhe disse?"),
        message_factory("Capitu me contou uma história, detetive.", "bentinho"),
    ))
    private = Conversation(id=uuid4(), game_id=game.id, participant_ids=("capitu", "escobar"),
                           created_at=game.created_at)
    await storage.memory.create_conversation(private)
    await storage.memory.append_messages(game.id, private.id, (
        message_factory("PRIVATE_NPC_DIALOGUE", "capitu"),
        message_factory("PRIVATE_REPLY", "escobar"),
    ))
    repository = RedisSocialRepository(storage.client, storage.prefix)
    view = SocialReadService(repository, storage.games, catalog)
    result = await view.reports(game.id)
    assert len(result.reports) == 1
    assert result.reports[0].content == "Capitu me contou uma história, detetive."
    assert "PRIVATE" not in result.model_dump_json()
    assert not {"knowledge", "relationships", "encounters"} & set(result.model_dump())


async def test_social_read_sanitizes_personal_secret_in_legacy_dialogue(
    storage, game, conversation, catalog, message_factory,
):
    secret = (await catalog.get("bentinho")).protected_secrets[0]
    await storage.memory.append_messages(game.id, conversation.id, (
        message_factory("O que faz?"), message_factory(secret, "bentinho"),
    ))
    view = SocialReadService(RedisSocialRepository(storage.client, storage.prefix), storage.games, catalog)
    assert secret not in (await view.reports(game.id)).model_dump_json()


async def test_social_routes_keep_private_knowledge_behind_admin_auth(
    api_client, storage, game, conversation, catalog, message_factory,
):
    from memorias_licantropicas.contracts.social import KnowledgeEntry
    from memorias_licantropicas.modules.admin.service import AdminService
    from memorias_licantropicas.modules.world.repository import RedisWorldRepository
    await storage.memory.append_messages(game.id, conversation.id, (
        message_factory("O que sabe?"), message_factory("Só rumores, detetive.", "bentinho"),
    ))
    repository = RedisSocialRepository(storage.client, storage.prefix)
    state = await repository.get(game.id)
    identifier = uuid4()
    entry = KnowledgeEntry(id=identifier, owner_id="capitu", root_id=identifier,
        source_message_id=uuid4(), speaker_id="virgilia", source_span="NPC_ONLY_GOSSIP",
        proposition="NPC_ONLY_GOSSIP", day=1, created_at=game.created_at)
    assert await repository.save(state.model_copy(update={"revision": 1, "knowledge": (entry,)}), 0)
    app = api_client._transport.app
    services = app.state.services
    app.state.services = replace(services,
        social_reads=SocialReadService(repository, storage.games, catalog),
        admin=AdminService(storage.client, storage.prefix, storage.games, catalog,
                           RedisWorldRepository(storage.client, storage.prefix), social_repository=repository))
    public = await api_client.get(f"/api/v1/games/{game.id}/social/reports")
    assert public.status_code == 200
    assert "NPC_ONLY_GOSSIP" not in public.text
    assert public.json()["reports"][0]["content"] == "Só rumores, detetive."
    private_path = f"/admin/api/v1/games/{game.id}/social"
    assert (await api_client.get(private_path)).status_code == 401
    response = await api_client.post("/admin/api/v1/auth/login", json={
        "username": "admin", "password": "test-admin-password",
    })
    assert response.status_code == 200
    private = await api_client.get(private_path)
    assert private.status_code == 200
    assert private.json()["knowledge"][0]["proposition"] == "NPC_ONLY_GOSSIP"
