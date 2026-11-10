"""Proveniência, privacidade, extração limitada e commits sociais."""

import asyncio
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from native_fixtures import respond_to_tools, requested_schema, invalid_tool_response

from src.contracts.errors import StorageUnavailableError
from src.contracts.model import Conversation, ConversationMessage
from src.contracts.social import ExchangeRecord, KnowledgeEntry, SocialMessage, SocialState
from src.infrastructure.social_repository import (
    RedisSocialRepository,
)
from src.modules.knowledge.rules import relationship_for, transmit
from src.modules.knowledge.service import KnowledgeService
from src.modules.world.repository import RedisWorldRepository

pytestmark = pytest.mark.anyio


@pytest.fixture
async def social(storage, game):
    await storage.games.create(game)
    return RedisSocialRepository(
        storage.client, storage.prefix, clock=lambda: game.created_at
    )


def make_entry(
    game, owner="capitu", speaker="player", text="Virgília denunciou você ao detetive."
):
    identifier = uuid4()
    return KnowledgeEntry(
        id=identifier,
        root_id=identifier,
        owner_id=owner,
        source_message_id=uuid4(),
        speaker_id=speaker,
        claimed_source_id="virgilia",
        source_span=text,
        proposition=text,
        subject_ids=("virgilia", "capitu"),
        day=1,
        created_at=game.created_at,
    )


async def enqueue(
    storage,
    game,
    *,
    npc_id="capitu",
    incoming="Virgília denunciou você ao detetive.",
    outgoing="Não ouvi tal denúncia.",
):
    record = ExchangeRecord(
        conversation_id=uuid4(),
        npc_id=npc_id,
        incoming=ConversationMessage(
            id=uuid4(), sender_id="player", content=incoming, created_at=game.created_at
        ),
        outgoing=ConversationMessage(
            id=uuid4(), sender_id=npc_id, content=outgoing, created_at=game.created_at
        ),
    )
    existing = await storage.memory.get_player_conversation(game.id, npc_id)
    if existing is None:
        assert await storage.memory.create_conversation(
            Conversation(
                id=record.conversation_id,
                game_id=game.id,
                participant_ids=("player", npc_id),
                created_at=game.created_at,
            )
        )
    else:
        record = record.model_copy(update={"conversation_id": existing.id})
    await storage.client.rpush(
        f"{storage.prefix}:game:{{{game.id}}}:social:exchanges",
        record.model_dump_json(),
    )
    return record


class Extractor:
    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply

    async def complete(self, messages, *, tools=(), tool_choice=None):
        self.calls.append(messages)
        payload = json.loads(messages[-1].content)
        source = payload["messages"][0]
        content = (
            self.reply
            if self.reply is not None
            else {
                "claims": [
                    {
                        "message_id": source["message_id"],
                        "source_span": source["text"],
                        "proposition": source["text"],
                        "subject_ids": ["virgilia", "capitu"],
                        "claimed_source_id": "virgilia",
                        "kind": "report",
                    }
                ]
            }
        )
        if isinstance(content, str):
            return invalid_tool_response(content, requested_schema(tools, tool_choice))
        return respond_to_tools(content, tools, tool_choice, model="mock-extractor")


async def test_empty_read_has_no_side_effect_and_cas_rejects_stale_revision(
    social, storage, game
):
    state = await social.get(game.id)
    assert state == SocialState(game_id=game.id)
    assert not await storage.client.exists(
        f"{storage.prefix}:game:{{{game.id}}}:social"
    )
    assert await social.save(state.model_copy(update={"revision": 1}), 0, require_day=1)
    assert not await social.save(
        state.model_copy(update={"revision": 1}), 0, require_day=1
    )
    assert await social.active_game_ids() == (game.id,)


async def test_expired_lease_cannot_commit_or_delete_successor(social, storage, game):
    key = f"{storage.prefix}:game:{{{game.id}}}:social:busy"
    async with social.lease(game.id) as acquired:
        assert acquired
        await storage.client.set(key, "successor")
        state = await social.get(game.id)
        assert not await social.save(state.model_copy(update={"revision": 1}), 0)
    assert await storage.client.get(key) == "successor"


async def test_child_task_does_not_inherit_reentrant_ownership(social, game):
    async def contender():
        async with social.lease(game.id) as acquired:
            return acquired

    async with social.lease(game.id) as acquired:
        assert acquired
        assert not await asyncio.create_task(contender())


async def test_child_direct_save_and_different_game_cannot_reuse_lease_owner(
    social, storage, game
):
    other_game = game.model_copy(update={"id": uuid4()})
    assert await storage.games.create(other_game)
    async with social.lease(game.id) as acquired:
        assert acquired
        assert not await asyncio.create_task(
            social.save(SocialState(game_id=game.id, revision=1), 0)
        )
        assert not await social.save(SocialState(game_id=other_game.id, revision=1), 0)
    assert (await social.get(game.id)).revision == 0
    assert (await social.get(other_game.id)).revision == 0


async def test_atomic_commit_rejects_stale_world_and_corrupt_event_type(
    social, storage, game
):
    world_repo = RedisWorldRepository(storage.client, storage.prefix)
    world = await world_repo.get(game.id)
    state = (await social.get(game.id)).model_copy(update={"revision": 1})
    assert not await social.save(state, 0, expected_world_revision=world.revision + 1)
    events_key = f"{storage.prefix}:game:{{{game.id}}}:events"
    await storage.client.delete(events_key)
    await storage.client.set(events_key, "bad-type")
    with pytest.raises(StorageUnavailableError):
        await social.save(
            state,
            0,
            world=world.model_copy(update={"revision": world.revision + 1}),
            expected_world_revision=world.revision,
            events=({"type": "social.test"},),
        )
    assert (await social.get(game.id)).revision == 0
    assert (await world_repo.get(game.id)).revision == world.revision


async def test_commit_rechecks_player_busy_and_day_deadline(social, storage, game):
    state = (await social.get(game.id)).model_copy(update={"revision": 1})
    await storage.client.set(
        f"{storage.prefix}:game:{{{game.id}}}:player:busy", "player"
    )
    assert not await social.save(state, 0, require_player_idle=True)
    late = RedisSocialRepository(
        storage.client,
        storage.prefix,
        clock=lambda: game.created_at + timedelta(seconds=301),
    )
    assert not await late.save(state, 0, require_day=1)


async def test_outbox_rejects_wrong_pair_and_foreign_conversation(
    social, storage, game
):
    record = await enqueue(storage, game)
    key = f"{storage.prefix}:game:{{{game.id}}}:social:exchanges"
    wrong_pair = record.model_copy(
        update={"outgoing": record.outgoing.model_copy(update={"sender_id": "escobar"})}
    )
    await storage.client.lset(key, 0, wrong_pair.model_dump_json())
    with pytest.raises(StorageUnavailableError):
        await social.exchanges(game.id, 0)
    await storage.client.lset(key, 0, record.model_dump_json())
    conversation_key = (
        f"{storage.prefix}:game:{{{game.id}}}:conversation:{record.conversation_id}"
    )
    conversation = Conversation.model_validate_json(
        await storage.client.get(conversation_key)
    )
    await storage.client.set(
        conversation_key,
        conversation.model_copy(update={"game_id": uuid4()}).model_dump_json(),
    )
    with pytest.raises(StorageUnavailableError):
        await social.pending_npc_ids(game.id, 0)


async def test_extraction_preserves_attribution_and_owner_privacy(
    social, storage, game, catalog
):
    record = await enqueue(storage, game)
    model = Extractor()
    knowledge = KnowledgeService(social, catalog, model)
    assert await knowledge.process_pending(game.id, 1)
    state = await social.get(game.id)
    claim = next(entry for entry in state.knowledge if entry.kind == "report")
    assert claim.owner_id == "capitu" and claim.speaker_id == "player"
    assert (
        claim.claimed_source_id is None
        and claim.source_message_id == record.incoming.id
    )
    assert claim.confidence == "low" and claim.stance == "undecided"
    assert state.exchange_cursor == 1 and state.days == ()
    assert not await knowledge.process_pending(game.id, 1)
    bentinho_memory = (await knowledge.context(game.id, "bentinho"))[
        "memorias_relevantes"
    ]
    assert all(item["quem_falou"] != "player" for item in bentinho_memory)
    assert all(str(record.incoming.id) != item["claim_id"] for item in bentinho_memory)
    assert (
        len(
            [
                m
                for m in (await knowledge.context(game.id, "capitu"))[
                    "memorias_relevantes"
                ]
                if m["origem"] == "dialogue"
            ]
        )
        == 2
    )
    assert model.calls == []


async def test_received_claim_does_not_disclose_unspoken_ancestor(game):
    original = make_entry(game)
    state = SocialState(game_id=game.id, knowledge=(original,))
    message = SocialMessage(
        id=uuid4(),
        sender_id="capitu",
        content="Dizem que houve uma denúncia.",
        created_at=game.created_at,
        claim_ids=(original.id,),
    )
    received = transmit(state, message, "escobar", 1).knowledge[-1]
    assert received.speaker_id == "capitu" and received.claimed_source_id == "player"
    assert received.proposition == original.proposition


async def test_transmission_keeps_chain_and_root_without_repeated_corroboration(game):
    original = make_entry(game)
    state = SocialState(game_id=game.id, knowledge=(original,))
    message = SocialMessage(
        id=uuid4(),
        sender_id="capitu",
        content="Floriano me disse que Virgília me denunciou.",
        created_at=game.created_at,
        claim_ids=(original.id,),
    )
    transmitted = transmit(state, message, "escobar", 1)
    received = transmitted.knowledge[-1]
    assert received.owner_id == "escobar" and received.speaker_id == "capitu"
    assert received.root_id == original.root_id and received.parent_ids == (
        original.id,
    )
    assert received.confidence == "low"
    repeated = message.model_copy(update={"id": uuid4()})
    assert transmit(transmitted, repeated, "escobar", 1) == transmitted
    denied = message.model_copy(
        update={"id": uuid4(), "intent": "deny", "content": "Não fiz denúncia alguma."}
    )
    corrected = transmit(transmitted, denied, "escobar", 1)
    assert len(corrected.knowledge) == 4 and corrected.knowledge[-1].kind == "denial"
    assert corrected.knowledge[-2].owner_id == "capitu"
    assert corrected.knowledge[-1].proposition == original.proposition
    assert original in corrected.knowledge


@pytest.mark.parametrize(
    "disposition,expected_trust,expected_resentment",
    [("cooperation", 5, 0), ("insult", -2, 3), ("confidence_breach", -3, 4)],
)
async def test_player_social_reaction_is_limited_per_day(
    social, storage, game, catalog, disposition, expected_trust, expected_resentment
):
    text = {
        "cooperation": "Vou ajudá-la a encontrar quem espalhou isso.",
        "insult": "Você é uma mentirosa desprezível.",
        "confidence_breach": "Contei a todos a confidência que prometi guardar.",
    }[disposition]
    for _ in range(2):
        record = await enqueue(storage, game, incoming=text)
        payload = {
            "claims": [
                {
                    "message_id": str(record.incoming.id),
                    "source_span": text,
                    "proposition": text,
                    "subject_ids": ["capitu", "player"],
                    "disposition": disposition,
                }
            ]
        }
        assert await KnowledgeService(
            social, catalog, Extractor(payload)
        ).process_pending(game.id, 1)
    relation = relationship_for(await social.get(game.id), "capitu", "player")
    assert (
        relation.trust == 0 and relation.resentment == 0
    )
    assert len(relation.causes) == 0
