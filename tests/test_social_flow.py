"""Cadeia real de fofoca: transcrição → memória → encontro → cobrança ao detetive."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from native_fixtures import respond_to_tools

from src.contracts.model import (
    Conversation,
    ConversationMessage,
    GameCharacter,
    GameState,
    LLMResponse,
)
from src.infrastructure.social_repository import (
    RedisSocialRepository,
)
from src.modules.agents.service import HarnessService
from src.modules.investigation.service import InvestigationService
from src.modules.knowledge.service import KnowledgeService
from src.modules.social.service import SocialService
from src.modules.social.views import SocialReadService
from src.modules.turns.service import TurnService
from src.modules.world.gate import RedisPlayerGate
from src.modules.world.repository import RedisWorldRepository
from src.modules.world.service import WorldService


pytestmark = pytest.mark.anyio


class RecordingLLM:
    def __init__(self, handler):
        self.handler, self.calls = handler, []

    async def complete(self, messages, *, tools=(), tool_choice=None):
        self.calls.append(messages)
        return respond_to_tools(
            self.handler(messages), tools, tool_choice, model="social-flow-stub"
        )


async def test_detective_accusation_circulates_with_provenance_and_returns_to_him(
    storage, catalog
):
    now = [datetime(2026, 11, 1, 12, tzinfo=UTC)]
    clock = lambda: now[0]
    profiles = await catalog.list()
    game = GameState(
        id=uuid4(),
        created_at=now[0],
        content_version=catalog.content_version,
        characters=tuple(
            GameCharacter(
                character_id=profile.id,
                role="werewolf" if profile.id == "bacamarte" else "civil",
            )
            for profile in profiles
        ),
    )
    assert await storage.games.create(game)
    world_repository = RedisWorldRepository(storage.client, storage.prefix)
    player_gate = RedisPlayerGate(storage.client, storage.prefix)
    turns = TurnService(
        storage.client,
        storage.prefix,
        storage.games,
        catalog,
        world_repository,
        player_gate,
        clock=clock,
    )
    investigation = InvestigationService(turns, catalog)
    repository = RedisSocialRepository(storage.client, storage.prefix, clock=clock)
    initial_case = await turns.sync(game.id)
    initial_game = await storage.games.get(game.id)

    # O dado confirmado é que Floriano fez uma afirmação; não há denúncia formal no motor.
    proposition = "Virgília denunciou Capitu ao delegado."
    incoming = ConversationMessage(
        id=uuid4(), sender_id="player", content=proposition, created_at=now[0]
    )
    capitu_reply = ConversationMessage(
        id=uuid4(),
        sender_id="capitu",
        content="O senhor me traz uma acusação; hei de pedir explicações a Virgília.",
        created_at=now[0],
    )
    conversation = Conversation(
        id=uuid4(),
        game_id=game.id,
        participant_ids=("player", "capitu"),
        created_at=now[0],
    )
    assert await storage.memory.create_conversation(conversation)
    await storage.memory.append_messages(
        game.id, conversation.id, (incoming, capitu_reply)
    )
    assert len(await repository.exchanges(game.id, 0)) == 1

    def extract(messages):
        source = json.loads(messages[-1].content)
        assert source["npc_id"] == "capitu"
        assert {item["speaker_id"] for item in source["messages"]} == {
            "player",
            "capitu",
        }
        return {
            "claims": [
                {
                    "message_id": str(incoming.id),
                    "source_span": proposition,
                    "proposition": proposition,
                    "subject_ids": ["capitu", "virgilia"],
                    "claimed_source_id": "virgilia",
                    "kind": "report",
                    "disposition": "accusation",
                }
            ]
        }

    extraction_llm = RecordingLLM(extract)
    knowledge = KnowledgeService(repository, catalog, extraction_llm, clock=clock)
    assert await knowledge.process_pending(game.id, 1)
    state = await repository.get(game.id)
    original = next(
        entry for entry in state.knowledge if entry.source_message_id == incoming.id
    )
    assert original.owner_id == "capitu" and original.speaker_id == "player"
    assert original.claimed_source_id is None and original.stance == "undecided"
    assert not [entry for entry in state.knowledge if entry.owner_id == "virgilia"]

    speeches = []

    def speak(messages):
        data = json.loads(messages[0].content.split("Dados: ", 1)[1])
        actor = data["ator"]
        claim = next(
            item
            for item in data["alegacoes_autorizadas"]
            if proposition in item["texto"]
        )
        quoted = claim["texto"]
        if actor == "capitu":
            assert data["destinatario"] == "virgilia"
        else:
            assert actor == "virgilia" and data["destinatario"] == "capitu"
        speeches.append(quoted)
        return {"intent": "repeat", "claim_ids": [claim["id"]]}

    social_llm = RecordingLLM(speak)
    social = SocialService(
        repository,
        knowledge,
        storage.games,
        catalog,
        world_repository,
        turns,
        social_llm,
        player_gate,
        clock=clock,
    )
    now[0] += timedelta(seconds=60)
    assert await social.tick(game.id)
    encounter = (await repository.get(game.id)).encounters[-1]
    assert encounter.participant_ids == ("capitu", "virgilia")
    assert encounter.phase == "travelling" and encounter.arrival_at > now[0]
    assert len(social_llm.calls) == 0
    now[0] = encounter.arrival_at + timedelta(milliseconds=1)
    assert await social.tick(game.id)  # Caminhada até Virgília; nenhuma fala duplicada.
    assert await social.tick(game.id)  # Capitu faz a cobrança.
    assert await social.tick(game.id)  # Virgília responde negando.
    state = await repository.get(game.id)
    encounter = state.encounters[-1]
    assert [item.sender_id for item in encounter.messages] == ["capitu", "virgilia"]
    assert len(extraction_llm.calls) == 0 and len(social_llm.calls) == 2
    received = next(
        entry
        for entry in state.knowledge
        if entry.owner_id == "virgilia"
        and entry.kind == "report"
        and entry.root_id == original.root_id
    )
    assert received.root_id == original.root_id and received.parent_ids == (
        original.id,
    )
    assert received.speaker_id == "capitu" and received.claimed_source_id == "player"
    assert received.proposition == original.proposition
    assert not any(entry.kind == "denial" for entry in state.knowledge)
    assert await turns.sync(game.id) == initial_case
    assert await storage.games.get(game.id) == initial_game

    # O caderno do jogador ainda só tem sua própria conversa; o encontro privado não foi ouvido.
    public = SocialReadService(repository, storage.games, catalog)
    before = await public.reports(game.id)
    assert [item.content for item in before.reports] == [capitu_reply.content]
    assert all(speech not in before.model_dump_json() for speech in speeches)

    world_service = WorldService(
        storage.games,
        catalog,
        world_repository,
        player_gate,
        day_policy=turns,
        clock=clock,
        on_approach=social.interrupt,
    )
    async with player_gate.hold(game.id):
        world = await world_repository.get(game.id)
        target = next(npc for npc in world.npcs if npc.npc_id == "virgilia")
        placed = world.model_copy(
            update={
                "revision": world.revision + 1,
                "player": world.player.model_copy(
                    update={"location_id": target.location_id, "x": target.x}
                ),
            }
        )
        assert await world_repository.save(placed, expected_revision=world.revision)
        await world_service.assert_can_talk(game.id, "virgilia")
    interrupted = (await repository.get(game.id)).encounters[-1]
    assert (
        interrupted.phase == "interrupted" and interrupted.reason == "player_approach"
    )
    assert len(interrupted.messages) == 2

    public_reply = "Capitu me contou sua acusação, Floriano. Quero que esclareça o que disse a ela."
    detective_llm = RecordingLLM(lambda messages: {"fala": public_reply})
    harness = HarnessService(
        catalog,
        storage.games,
        storage.memory,
        detective_llm,
        day_policy=turns,
        context_provider=investigation.npc_context_locked,
        knowledge_provider=knowledge.context,
    )
    async with player_gate.hold(game.id):
        reply = await harness.respond(
            game.id, "virgilia", uuid4(), "player", "Por que está aborrecida comigo?"
        )
    assert reply.message.content == public_reply
    prompt = detective_llm.calls[0][0].content
    projected = json.loads(prompt.split("Ficha privada:\n", 1)[1])
    memories = projected["observacoes_autorizadas"]["memoria_social"][
        "memorias_relevantes"
    ]
    assert any(
        proposition in entry["conteudo"] and entry["quem_falou"] == "capitu"
        for entry in memories
    )
    assert all(entry["tipo"] != "denial" for entry in memories)
    for profile in profiles:
        if profile.id != "virgilia":
            assert profile.bio not in prompt
            assert all(secret not in prompt for secret in profile.protected_secrets)
    reports = await public.reports(game.id)
    assert [entry.content for entry in reports.reports] == [
        capitu_reply.content,
        public_reply,
    ]
    assert not {"knowledge", "relationships", "encounters"} & set(reports.model_dump())
    assert await turns.sync(game.id) == initial_case
    assert await storage.games.get(game.id) == initial_game
