from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from src.contracts.errors import AccessDeniedError, ConflictError, NotFoundError
from src.contracts.investigation import CaseEvent
from src.contracts.model import GameCharacter, GameState
from src.modules.characters.repository import CatalogCharacterRepository
from src.modules.investigation.router import get_investigation_service, router
from src.modules.investigation.rules import evaluate_accusation, make_crime, make_initial_investigation
from src.modules.investigation.service import InvestigationService
from src.modules.world.catalog import make_initial_world

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

    async def act(self, game_id, transition, *, start_night_on_detention=False, allow_assembly=False):
        await self.require_day_locked(game_id)
        result = transition(self.state, self.game, self.world)
        updated = result.state
        starts_night = (start_night_on_detention and self.state.detained_npc_id is None
                        and updated.detained_npc_id is not None)
        if starts_night:
            assert any(record.accepted and record.suspect_id == updated.detained_npc_id
                       for record in updated.accusations[len(self.state.accusations):])
            updated = updated.model_copy(update={"phase": "night", "phase_ends_at": self.now() + timedelta(seconds=8)})
        if updated != self.state:
            self.state = updated.model_copy(update={"revision": self.state.revision + 1})
        self.events.extend(result.events)
        if starts_night:
            self.events.append(CaseEvent(type="night.started", data={"day": self.state.day, "reason": "accepted_detention"}))
        return self.state


@pytest.fixture
async def case():
    catalog = CatalogCharacterRepository()
    profiles = await catalog.list()
    game = GameState(id=uuid4(), created_at=NOW, content_version="3", characters=tuple(
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


async def complete_dossier(case):
    """Caso de duas manhãs; produz exame e corroboração pelos casos de uso reais."""
    await collect_all(case)
    second = make_crime(case.game, 1, "bras_cubas", "praca_verde", NOW)
    case.turns.state = case.turns.state.model_copy(update={"day": 2, "crimes": (*case.turns.state.crimes, second)})
    go_to(case)
    for _ in second.evidence:
        await case.service.search(case.game.id, second.id)
    evidence_ids = tuple(e.id for c in case.turns.state.crimes for e in c.evidence)
    for identifier in evidence_ids:
        await case.service.inspect(case.game.id, identifier)
    for member in case.game.characters:
        placement = next(n for n in case.turns.world.npcs if n.npc_id == member.character_id)
        go_to(case, placement.location_id, placement.x)
        for identifier in evidence_ids:
            await case.service.present(case.game.id, identifier, member.character_id)
    return case.turns.state


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
    state = await complete_dossier(case)
    public = await case.service.accuse(case.game.id, "capitu", tuple(item.id for crime in state.crimes for item in crime.evidence),
                                      tuple(item.id for item in state.testimonies))
    assert public.accusations[0].accepted and public.detained_npc_id == "capitu"
    assert public.ending is None and public.status == "active"
    assert public.phase == "night" and public.seconds_remaining == 8
    assert {event.type for event in case.turns.events} >= {"accusation.reviewed", "character.detained"}
    with pytest.raises(ConflictError):
        await case.service.accuse(case.game.id, "rubiao", (), ())


async def test_investigation_actions_integrate_with_atomic_turn_engine(case, storage, single_wolf_attack):
    from src.modules.turns.service import TurnService
    from src.modules.world.gate import RedisPlayerGate
    from src.modules.world.repository import RedisWorldRepository

    assert await storage.games.create(case.game)
    catalog = CatalogCharacterRepository()
    world_repository = RedisWorldRepository(storage.client, storage.prefix)
    clock = [NOW]
    turns = TurnService(storage.client, storage.prefix, storage.games, catalog, world_repository,
                        RedisPlayerGate(storage.client, storage.prefix), clock=lambda: clock[0])
    service = InvestigationService(turns, catalog)

    async def at(location, x):
        world = await world_repository.get(case.game.id)
        await world_repository.save(world.model_copy(update={"revision": world.revision + 1,
            "player": world.player.model_copy(update={"location_id": location, "x": x})}), world.revision)

    async def collect_and_hear(public):
        for crime in public.crimes:
            await at(crime.location_id, crime.x)
            for _ in range(crime.remaining_clues):
                public = await service.search(case.game.id, crime.id)
        for evidence in public.inventory:
            public = await service.inspect(case.game.id, evidence.id)
        world = await world_repository.get(case.game.id)
        living = {m.character_id for m in (await storage.games.get(case.game.id)).characters if m.alive}
        for npc in world.npcs:
            if npc.npc_id not in living:
                continue
            await at(npc.location_id, npc.x)
            for evidence in public.inventory:
                public = await service.present(case.game.id, evidence.id, npc.npc_id)
        return public

    public = await collect_and_hear(await service.get(case.game.id))
    public = await service.accuse(case.game.id, "capitu", tuple(item.id for item in public.inventory), tuple(item.id for item in public.testimonies))
    assert not public.accusations[-1].accepted and public.phase == "day"
    clock[0] = public.phase_ends_at
    assert (await service.get(case.game.id)).phase == "night"
    clock[0] += timedelta(seconds=8)
    public = await collect_and_hear(await service.get(case.game.id))
    members_before = (await storage.games.get(case.game.id)).characters
    public = await service.accuse(case.game.id, "capitu", tuple(item.id for item in public.inventory), tuple(item.id for item in public.testimonies))
    assert public.day == 2 and public.detained_npc_id == "capitu" and public.accusations[-1].accepted
    assert (await storage.games.get(case.game.id)).characters == members_before
    records = await storage.client.lrange(f"{storage.prefix}:game:{{{case.game.id}}}:events", 0, -1)
    assert sum('"type": "evidence.collected"' in record for record in records) == 4
    assert sum('"type": "evidence.examined"' in record for record in records) == 4


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
