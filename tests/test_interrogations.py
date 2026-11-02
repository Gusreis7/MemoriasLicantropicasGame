"""Regras investigativas: origem de álibis, confronto, dificuldade e transação final."""
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from memorias_licantropicas.contracts.errors import AccessDeniedError, ConflictError, NotFoundError
from memorias_licantropicas.contracts.investigation import CaseEvent, CaseTransition
from memorias_licantropicas.contracts.model import GameCharacter, GameState
from memorias_licantropicas.modules.investigation.interrogation import (
    CONFESSION_DIFFICULTY, make_confrontation, make_interrogation, npc_interrogation_context,
)
from memorias_licantropicas.modules.investigation.rules import make_crime, make_testimony
from memorias_licantropicas.modules.investigation.service import InvestigationService
from memorias_licantropicas.modules.turns.service import TurnService
from memorias_licantropicas.modules.world.gate import RedisPlayerGate
from memorias_licantropicas.modules.world.repository import RedisWorldRepository

pytestmark = pytest.mark.anyio


@pytest.fixture
async def inquiry(storage, catalog):
    now = [datetime(2026, 11, 1, 12, tzinfo=UTC)]
    profiles = await catalog.list()
    game = GameState(id=uuid4(), created_at=now[0], content_version=catalog.content_version,
        characters=tuple(GameCharacter(character_id=profile.id,
            role="werewolf" if profile.id == "capitu" else "civil") for profile in profiles))
    await storage.games.create(game)
    world = RedisWorldRepository(storage.client, storage.prefix)
    turns = TurnService(storage.client, storage.prefix, storage.games, catalog, world,
                        RedisPlayerGate(storage.client, storage.prefix), clock=lambda: now[0])
    return SimpleNamespace(game=game, clock=now, world=world, turns=turns,
        service=InvestigationService(turns, catalog), names={p.id: p.name for p in profiles},
        key=f"{storage.prefix}:game:{{{game.id}}}", storage=storage)


async def near(inquiry, npc_id):
    world = await inquiry.world.get(inquiry.game.id)
    placement = next(npc for npc in world.npcs if npc.npc_id == npc_id)
    await inquiry.world.save(world.model_copy(update={"revision": world.revision + 1,
        "player": world.player.model_copy(update={"location_id": placement.location_id, "x": placement.x})}),
        world.revision)


async def dossier(inquiry, wolf="capitu"):
    """Fixture com quatro crimes e todos vivos para isolar a regra de confissão."""
    state = await inquiry.turns.sync(inquiry.game.id)
    game = inquiry.game.model_copy(update={"characters": tuple(member.model_copy(update={
        "role": "werewolf" if member.character_id == wolf else "civil"}) for member in inquiry.game.characters)})
    # Fixture de regra pura; não altera o papel de uma partida persistida.
    crimes = tuple(make_crime(game, day, "bras_cubas", "praca_verde", inquiry.clock[0]) for day in range(4))
    crimes = tuple(crime.model_copy(update={"evidence": tuple(item.model_copy(update={"collected": True})
        for item in crime.evidence)}) for crime in crimes)
    state = state.model_copy(update={"crimes": crimes})
    statements = tuple(make_testimony(state, game, item, member.character_id, inquiry.names, inquiry.clock[0])
        for crime in crimes for item in crime.evidence for member in game.characters)
    state = state.model_copy(update={"testimonies": statements})
    interrogation = make_interrogation(state, game, wolf, 0, "night", inquiry.names, inquiry.clock[0])
    state = state.model_copy(update={"interrogations": (interrogation,)})
    return state, game, tuple(item.id for crime in crimes for item in crime.evidence), tuple(item.id for item in statements)


async def test_interrogation_needs_proximity_and_is_stable_without_truth_leak(inquiry):
    with pytest.raises(AccessDeniedError):
        await inquiry.service.interrogate(inquiry.game.id, "capitu", 0)
    await near(inquiry, "capitu")
    result = await inquiry.service.interrogate(inquiry.game.id, "capitu", 0)
    record = result.interrogations[0]
    assert record.npc_id == "capitu" and record.location_id is not None
    private = await inquiry.turns.sync(inquiry.game.id)
    assert private.interrogations[0].truthful is False
    assert all(term not in result.model_dump_json() for term in
               ("truthful", "source_record_ids", "activity_records", "pressure", "CONFESSION_DIFFICULTY"))
    assert await inquiry.service.interrogate(inquiry.game.id, "capitu", 0) == result


async def test_interrogation_rejects_future_period_and_transit(inquiry):
    await near(inquiry, "capitu")
    with pytest.raises(ConflictError):
        await inquiry.service.interrogate(inquiry.game.id, "capitu", 1, "night")
    with pytest.raises(ConflictError):
        await inquiry.service.interrogate(inquiry.game.id, "capitu", 2, "day")
    world = await inquiry.world.get(inquiry.game.id)
    world = world.model_copy(update={"revision": world.revision + 1, "npcs": tuple(
        member.model_copy(update={"activity": "travelling"}) if member.npc_id == "capitu" else member
        for member in world.npcs)})
    await inquiry.world.save(world, world.revision - 1)
    with pytest.raises(AccessDeniedError):
        await inquiry.service.interrogate(inquiry.game.id, "capitu", 0)


async def test_current_day_is_snapshot_and_past_without_record_admits_unknown(inquiry):
    await near(inquiry, "rubiao")
    result = await inquiry.service.interrogate(inquiry.game.id, "rubiao", 1, "day")
    saved = result.interrogations[0]
    assert saved.location_id == "praca_verde"
    # Sem retrospectiva inventada se uma partida antiga não tiver registros.
    state = await inquiry.turns.sync(inquiry.game.id)
    missing = state.model_copy(update={"activity_records": ()})
    record = make_interrogation(missing, inquiry.game, "rubiao", 0, "night", inquiry.names, inquiry.clock[0])
    assert record.location_id is None and record.observations == ()
    assert "lacuna" in record.text


async def test_civil_lacuna_and_individual_observation_limits(inquiry):
    await near(inquiry, "bacamarte")
    result = await inquiry.service.interrogate(inquiry.game.id, "bacamarte", 0)
    assert result.interrogations[0].location_id is None
    state = await inquiry.turns.sync(inquiry.game.id)
    for npc_id in inquiry.names:
        context = npc_interrogation_context(state, npc_id)
        for observation in context["observacoes_pessoais_de_presenca"]:
            assert any(record.npc_id == observation["personagem_id"] and npc_id in record.observed_by
                       for record in state.activity_records)
        assert "truthful" not in json.dumps(context)


@pytest.mark.parametrize("wolf", tuple(CONFESSION_DIFFICULTY))
async def test_every_persona_can_confess_under_sufficient_corroboration(inquiry, wolf):
    state, game, evidence_ids, testimony_ids = await dossier(inquiry, wolf)
    decision = make_confrontation(state, game, wolf, evidence_ids, testimony_ids,
        (state.interrogations[0].id,), inquiry.clock[0])
    assert decision.confessed and decision.pressure >= CONFESSION_DIFFICULTY[wolf]


async def test_pressure_is_public_evidence_based_and_civil_never_wins(inquiry):
    state, game, evidence_ids, testimony_ids = await dossier(inquiry)
    weak = make_confrontation(state, game, "capitu", (), (), (state.interrogations[0].id,), inquiry.clock[0])
    assert not weak.confessed
    actual = make_confrontation(state, game, "capitu", evidence_ids, testimony_ids,
        (state.interrogations[0].id,), inquiry.clock[0])
    civilian = game.model_copy(update={"characters": tuple(member.model_copy(update={
        "role": "werewolf" if member.character_id == "rubiao" else "civil"}) for member in game.characters)})
    refused = make_confrontation(state, civilian, "capitu", evidence_ids, testimony_ids,
        (state.interrogations[0].id,), inquiry.clock[0])
    assert actual.pressure == refused.pressure and not refused.confessed
    with pytest.raises(ConflictError):
        make_confrontation(state, game, "capitu", evidence_ids, testimony_ids, (), inquiry.clock[0])
    with pytest.raises(NotFoundError):
        make_confrontation(state, game, "capitu", evidence_ids, testimony_ids, (uuid4(),), inquiry.clock[0])


async def test_confrontation_daily_limit_and_missing_proof(inquiry):
    await near(inquiry, "capitu")
    record = (await inquiry.service.interrogate(inquiry.game.id, "capitu", 0)).interrogations[0]
    result = await inquiry.service.confront(inquiry.game.id, "capitu", interrogation_ids=(record.id,))
    assert result.status == "active" and not result.confrontations[0].confessed
    with pytest.raises(ConflictError):
        await inquiry.service.confront(inquiry.game.id, "capitu", interrogation_ids=(record.id,))


async def test_confession_commits_game_case_world_and_events_atomically(inquiry):
    state, _, evidence_ids, testimony_ids = await dossier(inquiry)
    # Instalar apenas a fixture de evidências; não alterar papéis nem prazos.
    await inquiry.storage.client.set(f"{inquiry.key}:investigation", state.model_dump_json())
    await near(inquiry, "capitu")
    result = await inquiry.service.confront(inquiry.game.id, "capitu", evidence_ids, testimony_ids,
                                             (state.interrogations[0].id,))
    assert result.status == "won" and result.phase == "finished" and result.ending.method == "confession"
    assert result.ending.werewolf_id == "capitu"
    assert (await inquiry.storage.games.get(inquiry.game.id)).status == "won"
    assert all(npc.npc_id != "capitu" for npc in (await inquiry.world.get(inquiry.game.id)).npcs)
    events = [json.loads(raw)["type"] for raw in await inquiry.storage.client.lrange(f"{inquiry.key}:events", 0, -1)]
    assert events.count("werewolf.confessed") == events.count("game.won") == 1
    with pytest.raises(ConflictError):
        await inquiry.service.interrogate(inquiry.game.id, "rubiao", 0)


async def test_forged_winning_transition_rejected(inquiry):
    def forge(state, game, world):
        return CaseTransition(state=state.model_copy(update={"status": "won", "phase": "finished",
            "ending_method": "confession"}), events=(CaseEvent(type="werewolf.confessed",
                data={"character_id": "capitu"}),))
    with pytest.raises(ValueError):
        await inquiry.turns.act(inquiry.game.id, forge)
    assert (await inquiry.storage.games.get(inquiry.game.id)).status == "active"


async def test_night_records_are_persisted_and_night_actions_blocked(inquiry):
    await near(inquiry, "capitu")
    inquiry.clock[0] += timedelta(seconds=300)
    with pytest.raises(ConflictError):
        await inquiry.service.interrogate(inquiry.game.id, "capitu", 0)
    inquiry.clock[0] += timedelta(seconds=8)
    state = await inquiry.turns.sync(inquiry.game.id)
    assert any(record.day == 1 and record.period == "night" and record.source == "night_resolution"
               for record in state.activity_records)
    assert all(record.source != "initial_scenario" for record in state.activity_records if record.day == 1)


async def test_snapshots_exclude_detained_and_travelling_characters(inquiry):
    from memorias_licantropicas.modules.investigation.interrogation import record_activities
    world = await inquiry.world.get(inquiry.game.id)
    world = world.model_copy(update={"npcs": tuple(npc.model_copy(update={"activity": "travelling"})
        if npc.npc_id == "virgilia" else npc for npc in world.npcs)})
    records = record_activities(inquiry.game, world, 1, "night", inquiry.clock[0], excluded_ids=("capitu",))
    assert all(record.npc_id not in {"capitu", "virgilia"} for record in records)
    assert all(not ({"capitu", "virgilia"} & set(record.observed_by + record.companion_ids)) for record in records)


async def test_alibi_text_template_and_memory_lapse_do_not_identify_role(inquiry):
    state = await inquiry.turns.sync(inquiry.game.id)
    for npc_id in ("capitu", "bacamarte"):
        civilian_game = inquiry.game.model_copy(update={"characters": tuple(member.model_copy(update={
            "role": "werewolf" if member.character_id == "rubiao" else "civil"}) for member in inquiry.game.characters)})
        wolf_game = inquiry.game.model_copy(update={"characters": tuple(member.model_copy(update={
            "role": "werewolf" if member.character_id == npc_id else "civil"}) for member in inquiry.game.characters)})
        civil = make_interrogation(state, civilian_game, npc_id, 0, "night", inquiry.names, inquiry.clock[0])
        wolf = make_interrogation(state, wolf_game, npc_id, 0, "night", inquiry.names, inquiry.clock[0])
        assert civil.activity == wolf.activity
        if npc_id == "bacamarte":
            assert civil.location_id is wolf.location_id is None and civil.text == wolf.text
        assert all(npc_id not in claim.companion_ids for claim in wolf.observations)


async def test_interrogate_and_confront_require_social_approach_first(inquiry):
    await near(inquiry, "capitu")
    world = await inquiry.world.get(inquiry.game.id)
    world = world.model_copy(update={"revision": world.revision + 1, "npcs": tuple(
        member.model_copy(update={"activity": "talking"}) if member.npc_id == "capitu" else member
        for member in world.npcs)})
    await inquiry.world.save(world, world.revision - 1)
    with pytest.raises(AccessDeniedError):
        await inquiry.service.interrogate(inquiry.game.id, "capitu", 0)
    with pytest.raises(AccessDeniedError):
        await inquiry.service.confront(inquiry.game.id, "capitu")


async def test_interrogation_rest_contract_disallows_client_truth(inquiry):
    import httpx
    from fastapi import FastAPI
    from memorias_licantropicas.modules.investigation.router import router, get_investigation_service
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_investigation_service] = lambda: inquiry.service
    await near(inquiry, "capitu")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        base = f"/api/v1/games/{inquiry.game.id}"
        result = await client.post(f"{base}/interrogations", json={"npc_id": "capitu", "day": 0, "period": "night"})
        assert result.status_code == 200 and len(result.json()["interrogations"]) == 1
        assert "truthful" not in result.text
        assert (await client.post(f"{base}/interrogations", json={"npc_id": "capitu", "day": 0,
            "location_id": "praca_verde"})).status_code == 422
        assert (await client.post(f"{base}/confrontations", json={"npc_id": "capitu", "confessed": True})).status_code == 422
