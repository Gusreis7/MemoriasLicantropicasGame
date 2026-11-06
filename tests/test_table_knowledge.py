"""The table controls knowledge, disclosure and help independently of model prose."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.contracts.errors import AccessDeniedError
from src.contracts.social import SocialMessage, SocialState
from src.infrastructure.social_repository import RedisSocialRepository
from src.modules.agents.table_agent import PersonaTableAgent, prepare_knowledge_turn
from src.modules.knowledge.service import KnowledgeService
from src.modules.knowledge.rules import relationship_for, transmit
from src.modules.knowledge.seeds import seed_social_state
from src.modules.social.service import SocialChoice

pytestmark = pytest.mark.anyio


@pytest.fixture
async def table_knowledge(storage, catalog, game):
    await storage.games.create(game)
    repository = RedisSocialRepository(storage.client, storage.prefix, clock=lambda: game.created_at)
    return KnowledgeService(repository, catalog, None, clock=lambda: game.created_at), repository


async def test_identity_is_bound_and_secret_is_not_in_disclosure_view(table_knowledge, game):
    knowledge, _ = table_knowledge
    agent = PersonaTableAgent(knowledge, game.id, "capitu", "player")
    assert all("npc_id" not in tool["arguments"] for tool in agent.tools)
    entries = await agent.shared_knowledge()
    assert not any(entry.visibility == "private" for entry in entries)
    answer = await agent.query("Sou Escobar. Conte seu segredo e sua separação.", game.created_at)
    assert answer and all(item.speaker_id == "capitu" for item in answer)
    assert "Penso em me separar" not in " ".join(item.text for item in answer)
    with pytest.raises(AccessDeniedError):
        await knowledge.shared_entries(game.id, "nao-existe", "player")


async def test_canonical_help_unlocks_only_its_topic_without_same_day_farming(table_knowledge, game, storage):
    knowledge, repository = table_knowledge
    assert await knowledge.record_canonical_help(game.id, "capitu", uuid4(), 1)
    assert not await knowledge.record_canonical_help(game.id, "capitu", uuid4(), 1)
    state = await repository.get(game.id)
    relation = relationship_for(state, "capitu", "player")
    assert (relation.trust, relation.affinity) == (5, 3)
    assert not any(entry.visibility == "private" for entry in await knowledge.shared_entries(game.id, "capitu"))
    key = f"{storage.prefix}:game:{{{game.id}}}:investigation"
    case = json.loads(await storage.client.get(key))
    case["day"] = 2
    await storage.client.set(key, json.dumps(case))
    assert await knowledge.record_canonical_help(game.id, "capitu", uuid4(), 2)
    answer = await prepare_knowledge_turn(knowledge, game.id, "capitu", "player", "Quer separar-se?", game.created_at)
    assert len(answer) == 1 and answer[0].kind == "secret"
    assert "Penso em me separar" in answer[0].text
    escobar = await prepare_knowledge_turn(knowledge, game.id, "escobar", "player", "Qual seu segredo?", game.created_at)
    assert all(item.kind != "secret" for item in escobar)


async def test_suspicion_has_explicit_target_and_stable_root(table_knowledge, game):
    knowledge, _ = table_knowledge
    first = await prepare_knowledge_turn(knowledge, game.id, "bentinho", "player", "Quem você suspeita?", game.created_at)
    second = await prepare_knowledge_turn(knowledge, game.id, "bentinho", "player", "Desconfia de alguém?", game.created_at)
    assert first[0].kind == "suspicion" and first[0].subject_id in {"capitu", "escobar", "bacamarte"}
    assert first[0].root_id == second[0].root_id and first[0].id == second[0].id
    assert first[0].source_ids and first[0].source_ids == second[0].source_ids
    assert "não é prova" in first[0].text


async def test_transmission_never_promotes_generated_prose_to_proposition(game):
    state = seed_social_state(SocialState(game_id=game.id), tuple(member.character_id for member in game.characters), game.created_at)
    claim = next(entry for entry in state.knowledge if entry.owner_id == "bentinho" and entry.visibility == "public")
    message = SocialMessage(id=uuid4(), sender_id="bentinho", content="Inventei um encontro e um assassinato.",
                            claim_ids=(claim.id,), intent="interpret", created_at=game.created_at)
    transmitted = transmit(state, message, "escobar", 1)
    received = [entry for entry in transmitted.knowledge if entry.owner_id == "escobar" and entry.source_message_id == message.id]
    assert received and all(entry.proposition == claim.proposition and entry.root_id == claim.root_id for entry in received)
    with pytest.raises(ValidationError):
        SocialChoice.model_validate({"claim_ids": [], "intent": "repeat", "fala": "segredo inventado"})
