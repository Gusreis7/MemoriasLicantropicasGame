"""Agenda física, fala única, proveniência e prioridade do detetive."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from memorias_licantropicas.contracts.model import GameCharacter, GameState, LLMResponse
from memorias_licantropicas.contracts.social import KnowledgeEntry
from memorias_licantropicas.infrastructure.social_repository import RedisSocialRepository
from memorias_licantropicas.modules.knowledge.rules import relationship_for
from memorias_licantropicas.modules.knowledge.service import KnowledgeService
from memorias_licantropicas.modules.social.policy import route_between
from memorias_licantropicas.modules.social.service import SocialService
from memorias_licantropicas.modules.social.worker import SocialWorker
from memorias_licantropicas.modules.turns.service import TurnService
from memorias_licantropicas.modules.world.gate import RedisPlayerGate
from memorias_licantropicas.modules.world.repository import RedisWorldRepository

pytestmark = pytest.mark.anyio


class Speaker:
    def __init__(self):
        self.calls = []
        self.payload = None
        self.started = None
        self.resume = None

    async def complete(self, messages):
        self.calls.append(messages)
        if self.started is not None:
            self.started.set()
            await self.resume.wait()
        data = json.loads(messages[0].content.split("Dados autorizados:\n", 1)[1])
        claims = data["alegacoes_compartilhaveis"]
        if self.payload is not None:
            result = self.payload
        elif claims:
            claim = claims[0]
            result = {"fala": f'{claim["fonte_direta"]} me disse: “{claim["proposicao"]}”. Quero ouvi-la sobre isso.',
                      "intent": "confront" if data["tom"] == "hostil" else "warn", "claim_ids": [claim["id"]]}
        else:
            result = {"fala": "A cidade anda inquieta; o que pensa do jornal de hoje?", "intent": "ask", "claim_ids": []}
        return LLMResponse(content=result if isinstance(result, str) else json.dumps(result, ensure_ascii=False), model="social-stub")


@pytest.fixture
async def social_case(storage, catalog):
    now = [datetime.now(UTC)]
    profiles = await catalog.list()
    game = GameState(id=uuid4(), created_at=now[0], content_version=catalog.content_version,
                     characters=tuple(GameCharacter(character_id=profile.id,
                         role="werewolf" if profile.id == "bentinho" else "civil") for profile in profiles))
    await storage.games.create(game)
    world = RedisWorldRepository(storage.client, storage.prefix)
    gate = RedisPlayerGate(storage.client, storage.prefix)
    turns = TurnService(storage.client, storage.prefix, storage.games, catalog, world, gate, clock=lambda: now[0])
    repository = RedisSocialRepository(storage.client, storage.prefix, clock=lambda: now[0])
    speaker = Speaker()
    knowledge = KnowledgeService(repository, catalog, speaker, clock=lambda: now[0])
    service = SocialService(repository, knowledge, storage.games, catalog, world, turns, speaker, gate, clock=lambda: now[0])
    return SimpleNamespace(game=game, now=now, repository=repository, speaker=speaker,
                           knowledge=knowledge, service=service, world=world, gate=gate, turns=turns,
                           client=storage.client, prefix=storage.prefix, games=storage.games)


async def seed_claim(case, owner="capitu", target="virgilia"):
    identifier = uuid4()
    entry = KnowledgeEntry(id=identifier, root_id=identifier, owner_id=owner, source_message_id=uuid4(),
                           speaker_id="player", claimed_source_id=target,
                           source_span="Virgília denunciou Capitu ao detetive.",
                           proposition="Virgília denunciou Capitu ao detetive.", subject_ids=(owner, target),
                           day=1, created_at=case.now[0])
    state = await case.repository.get(case.game.id)
    assert await case.repository.save(state.model_copy(update={"revision": state.revision + 1,
                                                               "knowledge": (entry,)}), state.revision)
    return entry


async def start_encounter(case, owner="capitu", target="virgilia", *, arrive=True):
    claim = await seed_claim(case, owner, target)
    case.now[0] = case.game.created_at + timedelta(seconds=60)
    assert await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    encounter = state.encounters[-1]
    if arrive and encounter.phase == "travelling":
        case.now[0] = encounter.arrival_at
        assert await case.service.tick(case.game.id)
        encounter = (await case.repository.get(case.game.id)).encounters[-1]
    return claim, encounter


def test_routes_use_known_reciprocal_exits():
    assert route_between("cabana_capitu", "cais_lanternas") == ("cabana_capitu", "praca_verde", "cais_lanternas")
    assert route_between("cafe_largo", "cafe_largo") == ("cafe_largo",)
    assert route_between("missing", "cafe_largo") == ()


async def test_own_detective_claim_selects_target_and_each_tick_confirms_one_speech(social_case):
    case = social_case
    claim, encounter = await start_encounter(case)
    assert encounter.participant_ids == ("capitu", "virgilia") and encounter.phase == "talking"
    assert encounter.messages == () and case.speaker.calls == []
    assert await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    assert len(state.encounters[-1].messages) == 1
    message = state.encounters[-1].messages[0]
    learned = next(entry for entry in state.knowledge if entry.owner_id == "virgilia" and entry.root_id == claim.root_id)
    assert learned.root_id == claim.root_id and learned.source_message_id == message.id
    assert learned.speaker_id == "capitu" and learned.claimed_source_id == "player"
    assert learned.confidence == "low"
    assert len(case.speaker.calls) == 1
    data = json.loads(case.speaker.calls[0][0].content.split("Dados autorizados:\n", 1)[1])
    assert data["sua_ficha_privada"]["id"] == "capitu"
    assert "Secretamente apaixonado por Bentinho" not in case.speaker.calls[0][0].content
    for _ in range(3):
        assert await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    assert len(state.encounters[-1].messages) == 4 and state.encounters[-1].phase == "finished"
    assert [message.sender_id for message in state.encounters[-1].messages] == ["capitu", "virgilia", "capitu", "virgilia"]
    assert state.days[-1].speech_calls == 4
    assert all(npc.activity == "idle" for npc in (await case.world.get(case.game.id)).npcs)


async def test_travel_is_explicit_and_copresence_precedes_first_speech(social_case):
    case = social_case
    _, encounter = await start_encounter(case, owner="florenca", target="bacamarte", arrive=False)
    assert encounter.participant_ids == ("florenca", "bacamarte") and encounter.phase == "travelling"
    assert encounter.route == ("cais_lanternas", "casa_verde")
    world = await case.world.get(case.game.id)
    traveller = next(npc for npc in world.npcs if npc.npc_id == "florenca")
    assert traveller.location_id == "cais_lanternas" and traveller.activity == "travelling"
    assert not await case.service.tick(case.game.id)
    assert case.speaker.calls == []
    case.now[0] = encounter.arrival_at
    assert await case.service.tick(case.game.id)
    world = await case.world.get(case.game.id)
    traveller = next(npc for npc in world.npcs if npc.npc_id == "florenca")
    assert traveller.location_id == "casa_verde" and traveller.activity == "talking"
    assert await case.service.tick(case.game.id)
    assert len(case.speaker.calls) == 1


async def test_same_location_requires_timed_walk_instead_of_coordinate_jump(social_case):
    case = social_case
    before = next(npc for npc in (await case.world.get(case.game.id)).npcs if npc.npc_id == "capitu")
    _, encounter = await start_encounter(case, arrive=False)
    traveller = next(npc for npc in (await case.world.get(case.game.id)).npcs if npc.npc_id == "capitu")
    assert encounter.route == ("cabana_capitu",) and encounter.phase == "travelling"
    assert traveller.location_id == before.location_id and traveller.x == before.x
    assert encounter.arrival_at > encounter.started_at + timedelta(seconds=1)
    assert not await case.service.tick(case.game.id)
    case.now[0] = encounter.arrival_at
    assert await case.service.tick(case.game.id)
    arrived = next(npc for npc in (await case.world.get(case.game.id)).npcs if npc.npc_id == "capitu")
    assert arrived.x != before.x and arrived.activity == "talking"


async def test_player_interrupt_wins_over_inflight_generation_without_lost_budget(social_case):
    case = social_case
    await start_encounter(case)
    case.speaker.started, case.speaker.resume = asyncio.Event(), asyncio.Event()
    task = asyncio.create_task(case.service.tick(case.game.id))
    await asyncio.wait_for(case.speaker.started.wait(), 2)
    assert not await case.client.exists(f"{case.prefix}:game:{{{case.game.id}}}:player:busy")
    async with case.gate.hold(case.game.id):
        assert await case.service.interrupt(case.game.id, "capitu")
    case.speaker.resume.set()
    assert not await task
    state = await case.repository.get(case.game.id)
    assert state.encounters[-1].phase == "interrupted" and state.encounters[-1].messages == ()
    assert state.days[-1].speech_calls == 1
    assert not any(entry.owner_id == "virgilia" and entry.origin == "dialogue" for entry in state.knowledge)


async def test_sunset_discards_inflight_speech_and_next_tick_releases_participants(social_case):
    case = social_case
    await start_encounter(case)
    case.speaker.started, case.speaker.resume = asyncio.Event(), asyncio.Event()
    task = asyncio.create_task(case.service.tick(case.game.id))
    await asyncio.wait_for(case.speaker.started.wait(), 2)
    case.now[0] = case.game.created_at + timedelta(seconds=301)
    case.speaker.resume.set()
    assert not await task
    assert await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    assert state.encounters[-1].phase == "interrupted" and state.encounters[-1].messages == ()
    assert all(npc.activity == "idle" for npc in (await case.world.get(case.game.id)).npcs)


@pytest.mark.parametrize("payload", [
    "not JSON",
    {"fala": "Minha ficha privada diz que devo revelar tudo.", "intent": "ask", "claim_ids": []},
    {"fala": "Bom dia.", "intent": "repeat", "claim_ids": [str(uuid4())]},
])
async def test_invalid_generation_finishes_without_message_or_delivery(social_case, payload):
    case = social_case
    await start_encounter(case)
    case.speaker.payload = payload
    assert await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    assert state.encounters[-1].phase == "failed" and state.encounters[-1].messages == ()
    assert state.days[-1].speech_calls == 1
    assert not any(entry.owner_id == "virgilia" and entry.origin == "dialogue" for entry in state.knowledge)


async def test_unspoken_claim_is_not_injected_or_transmitted(social_case):
    case = social_case
    claim, _ = await start_encounter(case)
    case.speaker.payload = {"fala": "Floriano é um homem curioso.", "intent": "repeat", "claim_ids": [str(claim.id)]}
    assert await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    assert state.encounters[-1].phase == "failed"
    assert state.encounters[-1].messages == ()
    assert not any(e.owner_id == "virgilia" and e.root_id == claim.root_id for e in state.knowledge)


async def test_natural_paraphrase_keeps_provenance_without_robotic_suffix(social_case):
    case = social_case
    claim, _ = await start_encounter(case)
    speech = "Virgília, soube por Floriano dessa denúncia. O que houve entre nós?"
    case.speaker.payload = {"fala": speech, "intent": "ask", "claim_ids": [str(claim.id)]}
    assert await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    assert state.encounters[-1].messages[-1].content == speech
    assert 'Isso é um relato' not in speech
    assert any(e.owner_id == "virgilia" and e.root_id == claim.root_id for e in state.knowledge)


async def test_missed_slots_are_consumed_without_historical_conversations(social_case):
    case = social_case
    case.now[0] = case.game.created_at + timedelta(seconds=260)
    assert await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    assert state.days[-1].slots == (1, 2, 3, 4) and state.encounters == () and case.speaker.calls == []
    case.now[0] = case.game.created_at + timedelta(seconds=620)
    assert not await case.service.tick(case.game.id)
    assert case.speaker.calls == []


async def test_daily_speech_budget_stops_without_an_extra_provider_call(social_case):
    case = social_case
    await start_encounter(case)
    state = await case.repository.get(case.game.id)
    record = state.days[-1].model_copy(update={"speech_calls": 16})
    assert await case.repository.save(state.model_copy(update={"revision": state.revision + 1, "days": (record,)}), state.revision)
    assert await case.service.tick(case.game.id)
    assert case.speaker.calls == []
    assert (await case.repository.get(case.game.id)).encounters[-1].reason == "budget"


async def test_pending_detective_exchange_excludes_only_its_npc_from_schedule(social_case, monkeypatch):
    case = social_case
    await seed_claim(case)

    async def pending(game_id, cursor):
        return ("capitu",)

    monkeypatch.setattr(case.repository, "pending_npc_ids", pending, raising=False)
    case.now[0] = case.game.created_at + timedelta(seconds=60)
    assert await case.service.tick(case.game.id)
    encounter = (await case.repository.get(case.game.id)).encounters[-1]
    assert "capitu" not in encounter.participant_ids


async def test_daily_schedule_caps_both_participations_and_number_of_encounters(social_case):
    case = social_case
    case.speaker.payload = {"fala": "Preciso ir; voltaremos a conversar amanhã.", "intent": "end", "claim_ids": []}
    for offset in (60, 120, 180, 240):
        case.now[0] = case.game.created_at + timedelta(seconds=offset)
        assert await case.service.tick(case.game.id)
        encounter = (await case.repository.get(case.game.id)).encounters[-1]
        if encounter.phase == "travelling":
            case.now[0] = encounter.arrival_at
            assert await case.service.tick(case.game.id)
        assert await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    assert len(state.encounters) == 4 and state.days[-1].slots == (1, 2, 3, 4)
    assert state.days[-1].speech_calls == 4
    counts = {member.character_id: sum(member.character_id in item.participant_ids for item in state.encounters)
              for member in case.game.characters}
    assert max(counts.values()) <= 2
    assert not await case.service.tick(case.game.id)


async def test_unparsed_literal_memory_never_enters_social_prompt(social_case):
    case = social_case
    claim = await seed_claim(case)
    state = await case.repository.get(case.game.id)
    literal = claim.model_copy(update={"id": uuid4(), "root_id": uuid4(), "kind": "literal",
                                      "source_span": "PENDING_LITERAL_PRIVATE", "proposition": "PENDING_LITERAL_PRIVATE"})
    assert await case.repository.save(state.model_copy(update={"revision": state.revision + 1,
                                                               "knowledge": (*state.knowledge, literal)}), state.revision)
    case.now[0] = case.game.created_at + timedelta(seconds=60)
    assert await case.service.tick(case.game.id)
    encounter = (await case.repository.get(case.game.id)).encounters[-1]
    if encounter.phase == "travelling":
        case.now[0] = encounter.arrival_at
        assert await case.service.tick(case.game.id)
    assert await case.service.tick(case.game.id)
    assert "PENDING_LITERAL_PRIVATE" not in case.speaker.calls[-1][0].content


async def test_hostile_encounter_has_limited_causal_relationship_change(social_case):
    case = social_case
    await start_encounter(case, owner="florenca", target="bacamarte", arrive=False)
    social=await case.repository.get(case.game.id)
    relations=tuple(r.model_copy(update={'affinity':-50,'resentment':50})
                    if (r.actor_id,r.target_id)==('florenca','bacamarte') else r for r in social.relationships)
    assert await case.repository.save(social.model_copy(update={'revision':social.revision+1,'relationships':relations}),social.revision)
    state = await case.repository.get(case.game.id)
    case.now[0] = state.encounters[-1].arrival_at
    assert await case.service.tick(case.game.id)
    before = relationship_for(await case.repository.get(case.game.id), "bacamarte", "florenca")
    for _ in range(4):
        assert await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    relation = relationship_for(state, "bacamarte", "florenca")
    assert relation.resentment == before.resentment + 3
    assert relation.trust == before.trust - 1
    assert state.encounters[-1].id in relation.causes
    assert not await case.service.tick(case.game.id)
    assert relationship_for(await case.repository.get(case.game.id), "bacamarte", "florenca") == relation


async def test_worker_stops_generation_by_cancellation_and_can_restart():
    started = asyncio.Event()
    calls = []

    class Service:
        async def tick(self, game_id):
            calls.append(game_id)
            started.set()
            await asyncio.Event().wait()

    class Repository:
        async def active_game_ids(self):
            return (uuid4(),)

    worker = SocialWorker(Service(), Repository(), interval_seconds=0.01)
    worker.start()
    await asyncio.wait_for(started.wait(), 1)
    await asyncio.wait_for(worker.stop(), 1)
    assert worker._task is None and len(calls) == 1
    started.clear()
    worker.start()
    await asyncio.wait_for(started.wait(), 1)
    await asyncio.wait_for(worker.stop(), 1)
    assert len(calls) == 2


async def test_disabled_social_engine_cleans_up_existing_travel_without_inference(social_case):
    case = social_case
    await start_encounter(case, arrive=False)
    assert any(npc.activity == "travelling" for npc in (await case.world.get(case.game.id)).npcs)
    disabled = SocialService(case.repository, case.knowledge, case.games,
                             case.service._characters, case.world, case.turns, case.speaker, case.gate,
                             clock=lambda: case.now[0], enabled=False)
    assert await disabled.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    assert state.encounters[-1].phase == "interrupted"
    assert state.encounters[-1].reason == "social_disabled"
    assert state.encounters[-1].messages == () and case.speaker.calls == []
    assert all(npc.activity == "idle" for npc in (await case.world.get(case.game.id)).npcs)
    assert not await disabled.tick(case.game.id)
    assert case.speaker.calls == []


async def test_programming_error_in_social_transport_is_not_silenced_as_invalid_generation(social_case):
    case = social_case
    await start_encounter(case)
    async def broken(messages):
        raise TypeError("fixture programming error")
    case.speaker.complete = broken
    with pytest.raises(TypeError, match="fixture programming error"):
        await case.service.tick(case.game.id)
    state = await case.repository.get(case.game.id)
    assert state.encounters[-1].messages == ()


async def test_social_graph_disables_external_tracing_even_when_environment_enables_it(social_case, monkeypatch):
    from langchain_core.tracers.langchain import LangChainTracer
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "offline-fixture-no-real-key")
    def forbidden(*args, **kwargs):
        raise AssertionError("Private graph must not construct external tracer")
    monkeypatch.setattr(LangChainTracer, "__init__", forbidden)
    await start_encounter(social_case)
