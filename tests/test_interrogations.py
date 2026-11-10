"""Regras investigativas: origem de álibis, confronto, dificuldade e transação final."""
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.contracts.errors import AccessDeniedError, ConflictError
from src.contracts.investigation import CaseEvent, CaseTransition
from src.contracts.model import GameCharacter, GameState
from src.modules.investigation.interrogation import make_interrogation
from src.modules.investigation.rules import make_crime, make_testimony, inspect_evidence
from src.modules.investigation.service import InvestigationService
from src.modules.turns.service import TurnService
from src.modules.world.gate import RedisPlayerGate
from src.modules.world.repository import RedisWorldRepository

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
    for crime in crimes:
        for item in crime.evidence:
            state = inspect_evidence(state, item.id, inquiry.clock[0]).state
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
    assert private.interrogations[0].truthful is True
    presence = next(item for night in private.table.nights if night.day == 0
                    for item in night.presences if item.npc_id == "capitu")
    assert private.interrogations[0].location_id == presence.location_id
    assert private.interrogations[0].companion_ids == presence.companion_ids
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
