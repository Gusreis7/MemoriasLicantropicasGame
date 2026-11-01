from collections import Counter
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from memorias_licantropicas.contracts.errors import AccessDeniedError, ConflictError, NotFoundError
from memorias_licantropicas.contracts.model import GameCharacter, GameState
from memorias_licantropicas.modules.characters.repository import CatalogCharacterRepository
from memorias_licantropicas.modules.investigation.catalog import INVENTORIES, ITEMS_BY_ID, OBSERVED_PEOPLE
from memorias_licantropicas.modules.investigation.router import get_investigation_service, router
from memorias_licantropicas.modules.investigation.rules import (
    choose_victim, evaluate_accusation, make_crime, make_initial_investigation, make_testimony,
)
from memorias_licantropicas.modules.investigation.service import InvestigationService
from memorias_licantropicas.modules.world.catalog import make_initial_world

pytestmark = pytest.mark.anyio
NOW = datetime(2026, 11, 2, 12, tzinfo=UTC)


class FakeTurns:
    def __init__(self, game):
        self.game, self.world = game, make_initial_world(game.id)
        self.state, self.events = make_initial_investigation(game, NOW), []
        self.time = NOW
        self.sync_calls = 0
        self.locked_calls = 0

    def now(self):
        return self.time

    async def sync(self, game_id):
        assert game_id == self.game.id
        self.sync_calls += 1
        return self.state

    async def require_day_locked(self, game_id):
        assert game_id == self.game.id
        self.locked_calls += 1
        if self.state.phase != "day" or self.state.status != "active":
            raise ConflictError("Dia encerrado.")
        return self.state

    async def act(self, game_id, transition):
        await self.require_day_locked(game_id)
        result = transition(self.state, self.game, self.world)
        if result.state != self.state:
            self.state = result.state.model_copy(update={"revision": self.state.revision + 1})
        self.events.extend(result.events)
        return self.state


@pytest.fixture
async def case():
    catalog = CatalogCharacterRepository()
    profiles = await catalog.list()
    game = GameState(id=uuid4(), created_at=NOW, content_version="2", characters=tuple(
        GameCharacter(character_id=profile.id, role="werewolf" if profile.id == "capitu" else "civil")
        for profile in profiles))
    turns = FakeTurns(game)
    service = InvestigationService(turns, catalog)
    names = {profile.id: profile.name for profile in profiles}
    return SimpleNamespace(game=game, turns=turns, service=service, names=names)


def go_to(case, location="praca_verde", x=600):
    case.turns.world = case.turns.world.model_copy(update={"player": case.turns.world.player.model_copy(
        update={"location_id": location, "x": x})})


async def collect_all(case):
    go_to(case)
    crime = case.turns.state.crimes[0]
    await case.service.search(case.game.id, crime.id)
    return await case.service.search(case.game.id, crime.id)


async def submit_testimonies(case, npc="bentinho"):
    await collect_all(case)
    placement = next(n for n in case.turns.world.npcs if n.npc_id == npc)
    go_to(case, placement.location_id, placement.x)
    for evidence in case.turns.state.crimes[0].evidence:
        await case.service.present(case.game.id, evidence.id, npc)
    return case.turns.state


async def test_inventory_has_five_items_and_shared_pools_are_balanced():
    assert len(INVENTORIES) == 7 and len(ITEMS_BY_ID) == 20
    owners = Counter(item for items in INVENTORIES.values() for item in items)
    for inventory in INVENTORIES.values():
        assert len(inventory) == len(set(inventory)) == 5
        assert Counter(ITEMS_BY_ID[item].kind for item in inventory) == {"unique": 1, "singular": 1, "common": 3}
    assert len([item for item in ITEMS_BY_ID.values() if item.kind == "common"]) == 10
    for item in ITEMS_BY_ID.values():
        assert owners[item.id] == 1 if item.kind == "unique" else 2 <= owners[item.id] <= 3


async def test_initial_crime_and_later_distinctive_clues_are_rule_generated(case):
    state = case.turns.state
    assert state.day == 1 and (state.phase_ends_at - NOW).total_seconds() == 300
    assert state.crimes[0].victim_id == "bras_cubas"
    assert state.crimes[0].location_id == "praca_verde" and state.crimes[0].x == 600
    assert {item.deposited_by for item in state.crimes[0].evidence} == {"capitu"}
    assert {ITEMS_BY_ID[item.item_id].kind for item in state.crimes[0].evidence} == {"common", "singular"}
    crime = make_crime(case.game, 3, "escobar", "cafe_largo", NOW)
    assert {ITEMS_BY_ID[item.item_id].kind for item in crime.evidence} == {"common", "unique"}


@pytest.mark.parametrize("wolf,target", [
    ("bentinho", "escobar"), ("capitu", "escobar"), ("escobar", "capitu"),
    ("rubiao", "virgilia"), ("virgilia", "rubiao"), ("florenca", "bacamarte"),
])
async def test_victim_preference_respects_canon_and_eligibility(case, wolf, target):
    game = case.game.model_copy(update={"characters": tuple(npc.model_copy(update={
        "role": "werewolf" if npc.character_id == wolf else "civil"}) for npc in case.game.characters)})
    assert choose_victim(game) == target
    assert choose_victim(game, target) not in {target, wolf, "player"}
    dead = game.model_copy(update={"characters": tuple(npc.model_copy(update={"alive": False})
        if npc.role == "civil" else npc for npc in game.characters)})
    assert choose_victim(dead) is None


async def test_public_projection_hides_uncollected_items_and_private_fields(case):
    public = await case.service.get(case.game.id)
    assert public.inventory == () and public.ending is None
    assert public.journal[0].title == "O Clarim do Rio"
    assert public.crimes[0].remaining_clues == 2
    text = public.model_dump_json()
    assert all(field not in text for field in ("killer_id", "deposited_by", "truthful", "werewolf_id", "fita_veludo"))
    assert case.turns.sync_calls == 1


async def test_search_requires_location_proximity_and_collects_exactly_once(case):
    crime = case.turns.state.crimes[0]
    with pytest.raises(AccessDeniedError):
        await case.service.search(case.game.id, crime.id)
    go_to(case, "casa_verde", 600)
    with pytest.raises(AccessDeniedError):
        await case.service.search(case.game.id, crime.id)
    go_to(case, x=510)
    first = await case.service.search(case.game.id, crime.id)
    assert len(first.inventory) == 1 and first.crimes[0].remaining_clues == 1
    second = await case.service.search(case.game.id, crime.id)
    assert len(second.inventory) == 2 and second.crimes[0].remaining_clues == 0
    repeated = await case.service.search(case.game.id, crime.id)
    assert repeated == second
    assert len(case.turns.events) == 2
    with pytest.raises(NotFoundError):
        await case.service.search(case.game.id, uuid4())


async def test_presentation_requires_real_collected_item_and_near_living_free_npc(case):
    evidence = case.turns.state.crimes[0].evidence[0]
    with pytest.raises(ConflictError):
        await case.service.present(case.game.id, evidence.id, "bentinho")
    await collect_all(case)
    with pytest.raises(AccessDeniedError):
        await case.service.present(case.game.id, evidence.id, "bentinho")
    go_to(case, "cafe_largo", 460)
    case.turns.state = case.turns.state.model_copy(update={"detained_npc_id": "bentinho"})
    with pytest.raises(AccessDeniedError):
        await case.service.present(case.game.id, evidence.id, "bentinho")
    case.turns.state = case.turns.state.model_copy(update={"detained_npc_id": None})
    case.turns.game = case.game.model_copy(update={"characters": tuple(npc.model_copy(update={"alive": False})
        if npc.character_id == "bentinho" else npc for npc in case.game.characters)})
    with pytest.raises(AccessDeniedError):
        await case.service.present(case.game.id, evidence.id, "bentinho")


async def test_presentation_is_stable_and_common_recognition_does_not_claim_origin(case):
    await collect_all(case)
    evidence = case.turns.state.crimes[0].evidence[0]
    go_to(case, "cafe_largo", 460)
    first = await case.service.present(case.game.id, evidence.id, "bentinho")
    record = first.testimonies[0]
    assert record.recognition == "recognizes" and record.claimed_owner_id == "capitu"
    assert "não prova" in record.text
    assert "truthful" not in first.model_dump_json()
    second = await case.service.present(case.game.id, evidence.id, "bentinho")
    assert second == first and len(second.testimonies) == 1


async def test_wolf_can_deny_without_revealing_role_to_client(case):
    await collect_all(case)
    go_to(case, "cabana_capitu", 440)
    evidence = case.turns.state.crimes[0].evidence[0]
    public = await case.service.present(case.game.id, evidence.id, "capitu")
    assert public.testimonies[0].recognition == "denies"
    assert public.testimonies[0].claimed_owner_id is None
    assert case.turns.state.testimonies[0].truthful is False
    assert "truthful" not in public.model_dump_json()


async def test_unknown_witness_does_not_invent_provenance(case):
    await collect_all(case)
    rare = case.turns.state.crimes[0].evidence[1]
    go_to(case, "casa_verde", 460)
    public = await case.service.present(case.game.id, rare.id, "bacamarte")
    # Bacamarte observa Bentinho e Capitu; portanto conhece esta posse observada.
    assert public.testimonies[0].claimed_owner_id == "capitu"
    unique = make_crime(case.game, 3, "escobar", "cafe_largo", NOW).evidence[1]
    unknown = make_testimony(case.turns.state, case.game, unique, "rubiao", case.names, NOW)
    assert unknown.recognition == "unknown" and unknown.claimed_owner_id is None


async def test_delegate_accepts_corroboration_and_is_blind_to_private_origin_or_truthfulness(case):
    state = await submit_testimonies(case)
    evidence_ids = tuple(item.id for item in state.crimes[0].evidence)
    testimony_ids = tuple(item.id for item in state.testimonies)
    decision = evaluate_accusation(state, "capitu", evidence_ids, testimony_ids, NOW)
    assert decision.accepted
    # Um testemunho enganoso pode convencer; o delegado não consulta o dono real.
    changed = state.model_copy(update={"crimes": tuple(crime.model_copy(update={"killer_id": "rubiao", "evidence": tuple(
        item.model_copy(update={"deposited_by": "rubiao"}) for item in crime.evidence)}) for crime in state.crimes),
        "testimonies": tuple(item.model_copy(update={"truthful": False}) for item in state.testimonies)})
    blinded = evaluate_accusation(changed, "capitu", evidence_ids, testimony_ids, NOW)
    assert blinded.accepted == decision.accepted and blinded.reason == decision.reason


async def test_delegate_rejects_repetition_unlinked_items_and_bare_accusations(case):
    state = await submit_testimonies(case)
    evidence_ids = tuple(item.id for item in state.crimes[0].evidence)
    testimony_ids = tuple(item.id for item in state.testimonies)
    assert not evaluate_accusation(state, "capitu", (evidence_ids[0],) * 20, (testimony_ids[0],) * 20, NOW).accepted
    assert not evaluate_accusation(state, "rubiao", evidence_ids, testimony_ids, NOW).accepted
    assert not evaluate_accusation(state, "capitu", evidence_ids, (), NOW).accepted
    with pytest.raises(NotFoundError):
        evaluate_accusation(state, "capitu", evidence_ids, (uuid4(),), NOW)
    with pytest.raises(ConflictError):
        evaluate_accusation(state, "capitu", (evidence_ids[0],), (testimony_ids[1],), NOW)


async def test_accusation_detains_and_consumes_only_one_attempt_per_day(case):
    state = await submit_testimonies(case)
    public = await case.service.accuse(case.game.id, "capitu", tuple(item.id for item in state.crimes[0].evidence),
                                      tuple(item.id for item in state.testimonies))
    assert public.accusations[0].accepted and public.detained_npc_id == "capitu"
    assert public.ending is None and public.status == "active"
    assert {event.type for event in case.turns.events} >= {"accusation.reviewed", "character.detained"}
    with pytest.raises(ConflictError):
        await case.service.accuse(case.game.id, "rubiao", (), ())


async def test_refusal_does_not_detain_and_dead_testimony_remains_usable(case):
    public = await case.service.accuse(case.game.id, "capitu", (), ())
    assert not public.accusations[0].accepted and public.detained_npc_id is None
    case.turns.state = case.turns.state.model_copy(update={"day": 2})
    await submit_testimonies(case)
    case.turns.game = case.game.model_copy(update={"characters": tuple(npc.model_copy(update={"alive": False})
        if npc.character_id == "bentinho" else npc for npc in case.game.characters)})
    state = case.turns.state
    public = await case.service.accuse(case.game.id, "capitu", tuple(item.id for item in state.crimes[0].evidence),
                                      tuple(item.id for item in state.testimonies))
    assert public.accusations[-1].accepted


@pytest.mark.parametrize("wolf", tuple(INVENTORIES))
async def test_every_wolf_has_an_initial_deduction_path_with_living_civil_observers(case, wolf):
    game = case.game.model_copy(update={"characters": tuple(npc.model_copy(update={
        "role": "werewolf" if npc.character_id == wolf else "civil"}) for npc in case.game.characters)})
    state = make_initial_investigation(game, NOW)
    crime = state.crimes[0].model_copy(update={"evidence": tuple(item.model_copy(update={"collected": True})
        for item in state.crimes[0].evidence)})
    records = tuple(make_testimony(state, game, item, npc.character_id, case.names, NOW)
        for item in crime.evidence for npc in game.characters if npc.character_id != wolf)
    state = state.model_copy(update={"crimes": (crime,), "testimonies": records})
    decision = evaluate_accusation(state, wolf, tuple(item.id for item in crime.evidence), tuple(record.id for record in records), NOW)
    assert decision.accepted


async def test_npc_context_uses_existing_lock_and_limits_observed_inventory(case):
    context = await case.service.npc_context_locked(case.game.id, "bentinho")
    assert case.turns.locked_calls == 1 and case.turns.sync_calls == 0
    assert len(context["proprios_apetrechos"]) == 5
    assert {record["personagem_id"] for record in context["posses_observadas"]} == set(OBSERVED_PEOPLE["bentinho"])
    assert len(context["posses_observadas"]) == 2
    assert all(key not in str(context) for key in ("killer_id", "truthful", "role", "werewolf"))


async def test_investigation_actions_integrate_with_atomic_turn_engine(case, storage):
    from memorias_licantropicas.modules.turns.service import TurnService
    from memorias_licantropicas.modules.world.gate import RedisPlayerGate
    from memorias_licantropicas.modules.world.repository import RedisWorldRepository

    assert await storage.games.create(case.game)
    catalog = CatalogCharacterRepository()
    world_repository = RedisWorldRepository(storage.client, storage.prefix)
    turns = TurnService(storage.client, storage.prefix, storage.games, catalog, world_repository,
                        RedisPlayerGate(storage.client, storage.prefix), clock=lambda: NOW)
    service = InvestigationService(turns, catalog)
    public = await service.get(case.game.id)
    world = await world_repository.get(case.game.id)
    await world_repository.save(world.model_copy(update={"revision": world.revision + 1,
        "player": world.player.model_copy(update={"x": 600})}), expected_revision=world.revision)
    public = await service.search(case.game.id, public.crimes[0].id)
    public = await service.search(case.game.id, public.crimes[0].id)
    world = await world_repository.get(case.game.id)
    await world_repository.save(world.model_copy(update={"revision": world.revision + 1,
        "player": world.player.model_copy(update={"location_id": "cafe_largo", "x": 460})}), expected_revision=world.revision)
    for evidence in public.inventory:
        public = await service.present(case.game.id, evidence.id, "bentinho")
    unchanged = await service.present(case.game.id, public.inventory[0].id, "bentinho")
    assert unchanged.revision == public.revision
    public = await service.accuse(case.game.id, "capitu", tuple(item.id for item in public.inventory),
                                  tuple(item.id for item in public.testimonies))
    assert public.detained_npc_id == "capitu" and public.accusations[-1].accepted
    assert (await storage.games.get(case.game.id)).characters == case.game.characters
    records = await storage.client.lrange(f"{storage.prefix}:game:{{{case.game.id}}}:events", 0, -1)
    assert sum('"type": "evidence.collected"' in record for record in records) == 2


async def test_rest_commands_reject_client_truth_and_return_only_public_case(case):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_investigation_service] = lambda: case.service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        base = f"/api/v1/games/{case.game.id}"
        result = await client.get(f"{base}/investigation")
        assert result.status_code == 200 and result.json()["inventory"] == []
        assert (await client.post(f"{base}/accusations", json={"suspect_id": "capitu", "accepted": True})).status_code == 422
        evidence = case.turns.state.crimes[0].evidence[0]
        assert (await client.post(f"{base}/evidence/{evidence.id}/present", json={"npc_id": "bentinho", "truthful": True})).status_code == 422
        crime = case.turns.state.crimes[0]
        assert (await client.post(f"{base}/crime-scenes/{crime.id}/search", json={"item_id": "leque_vn"})).status_code == 422
