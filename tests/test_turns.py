import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.contracts.errors import ConflictError, NotFoundError, StorageUnavailableError
from src.contracts.investigation import CaseEvent, CaseTransition
from src.contracts.model import GameCharacter, GameState
from src.modules.turns.service import TurnService
from src.modules.world.gate import RedisPlayerGate
from src.modules.world.repository import RedisWorldRepository

pytestmark = pytest.mark.anyio


@pytest.fixture
async def cycle(storage, catalog, single_wolf_attack):
    now = [datetime(2026, 11, 1, 12, tzinfo=UTC)]
    profiles = await catalog.list()
    game = GameState(id=uuid4(), created_at=now[0], content_version=catalog.content_version,
                     characters=tuple(GameCharacter(character_id=profile.id,
                         role="werewolf" if profile.id == "bentinho" else "civil") for profile in profiles))
    await storage.games.create(game)
    world = RedisWorldRepository(storage.client, storage.prefix)
    gate = RedisPlayerGate(storage.client, storage.prefix)
    turns = TurnService(storage.client, storage.prefix, storage.games, catalog, world, gate,
                        clock=lambda: now[0])
    return SimpleNamespace(game=game, clock=now, turns=turns, world=world, gate=gate,
                           key=f"{storage.prefix}:game:{{{game.id}}}")


async def events(storage, cycle, event_type=None):
    records = [json.loads(raw) for raw in await storage.client.lrange(f"{cycle.key}:events", 0, -1)]
    return [record for record in records if event_type is None or record["type"] == event_type]


async def detain(cycle, suspect):
    def transition(state, _game, _world):
        return CaseTransition(state=state.model_copy(update={"detained_npc_id": suspect}),
                              events=(CaseEvent(type="suspect.detained", data={"suspect_id": suspect}),))
    return await cycle.turns.act(cycle.game.id, transition)


async def test_bootstrap_initializes_clock_without_extra_events_and_no_get_writes(cycle, storage):
    before = await storage.client.get(f"{cycle.key}:investigation")
    case = await cycle.turns.sync(cycle.game.id)
    assert case.phase == "day" and case.day == 1 and case.status == "active"
    assert case.phase_ends_at == cycle.clock[0] + timedelta(seconds=300)
    assert len(case.crimes) == 1 and case.crimes[0].victim_id == "bras_cubas"
    assert len(await events(storage, cycle)) == 3
    assert await storage.client.get(f"{cycle.key}:investigation") == before


async def test_day_deadline_begins_non_playable_night_and_stops_world(cycle, storage):
    initial = await cycle.turns.sync(cycle.game.id)
    cycle.clock[0] += timedelta(seconds=299, milliseconds=999)
    assert (await cycle.turns.sync(cycle.game.id)).phase == "day"
    cycle.clock[0] += timedelta(milliseconds=1)
    case = await cycle.turns.sync(cycle.game.id)
    assert case.phase == "night" and case.day == 1
    assert case.phase_ends_at == cycle.clock[0] + timedelta(seconds=8)
    assert case.revision == initial.revision + 1
    assert len(await events(storage, cycle, "night.started")) == 1
    assert not await events(storage, cycle, "character.killed")
    async with cycle.gate.hold(cycle.game.id):
        with pytest.raises(ConflictError):
            await cycle.turns.require_day_locked(cycle.game.id)
    with pytest.raises(ConflictError):
        await cycle.turns.act(cycle.game.id, lambda state, *_: CaseTransition(state=state))
    assert (await cycle.world.get(cycle.game.id)).player.direction == "idle"


async def test_morning_commits_victim_clues_game_alive_and_newsstand_atomically(cycle, storage):
    before = await cycle.world.get(cycle.game.id)
    moved = before.model_copy(update={"revision": before.revision + 1,
        "player": before.player.model_copy(update={"location_id": "cais_lanternas", "x": 700,
            "movement_seq": 21, "direction": "left", "facing": "left"})})
    await cycle.world.save(moved, expected_revision=before.revision)
    cycle.clock[0] += timedelta(seconds=308)
    case = await cycle.turns.sync(cycle.game.id)
    assert case.phase == "day" and case.day == 2
    assert case.phase_ends_at == cycle.clock[0] + timedelta(seconds=300)
    crime = case.crimes[-1]
    assert crime.victim_id == "escobar"  # Objetivo canônico de Bentinho.
    assert crime.killer_id == "bentinho" and crime.evidence
    game = await storage.games.get(cycle.game.id)
    assert not next(member for member in game.characters if member.character_id == "escobar").alive
    assert tuple((member.character_id, member.role) for member in game.characters) == tuple(
        (member.character_id, member.role) for member in cycle.game.characters)
    morning = await cycle.world.get(cycle.game.id)
    assert morning.player.location_id == "praca_verde" and morning.player.x == 160
    assert morning.player.facing == "right" and morning.player.direction == "idle"
    assert morning.player.movement_seq == 21 and morning.revision == moved.revision + 2
    assert case.journal[-1].victim_id == crime.victim_id
    killed = await events(storage, cycle, "character.killed")
    assert len(killed) == 1 and killed[0]["source"] == "rules"
    assert killed[0]["occurred_at"] == cycle.clock[0].isoformat()
    unchanged = await cycle.turns.sync(cycle.game.id)
    assert unchanged == case and len(await events(storage, cycle, "character.killed")) == 1


async def test_detained_werewolf_transforms_wins_and_is_expelled(cycle, storage):
    await detain(cycle, "bentinho")
    cycle.clock[0] += timedelta(seconds=308)
    case = await cycle.turns.sync(cycle.game.id)
    game = await storage.games.get(cycle.game.id)
    assert case.status == game.status == "won" and case.phase == "finished"
    assert case.journal[-1].detention_outcome == "transformed"
    assert case.journal[-1].victim_id is None
    assert len(case.crimes) == 1 and all(member.alive for member in game.characters)
    assert len(await events(storage, cycle, "werewolf.expelled")) == 1
    assert not await events(storage, cycle, "character.killed")
    cycle.clock[0] += timedelta(days=1)
    assert await cycle.turns.sync(cycle.game.id) == case
    with pytest.raises(ConflictError):
        await cycle.turns.act(cycle.game.id, lambda state, *_: CaseTransition(state=state))


async def test_innocent_detention_protects_only_detainee_and_releases_at_morning(cycle, storage):
    await detain(cycle, "escobar")
    cycle.clock[0] += timedelta(seconds=308)
    case = await cycle.turns.sync(cycle.game.id)
    assert case.status == "active" and case.detained_npc_id is None
    assert case.journal[-1].detention_outcome == "released"
    assert case.crimes[-1].victim_id != "escobar"
    game = await storage.games.get(cycle.game.id)
    assert next(member for member in game.characters if member.character_id == "escobar").alive
    assert len(await events(storage, cycle, "suspect.released")) == 1


async def test_last_civil_in_jail_yields_no_death_but_following_unprotected_night_loses(cycle, storage):
    game = cycle.game.model_copy(update={"characters": tuple(
        member if member.role == "werewolf" or member.character_id == "escobar"
        else member.model_copy(update={"alive": False}) for member in cycle.game.characters)})
    await storage.client.set(f"{cycle.key}:state", game.model_dump_json())
    await detain(cycle, "escobar")
    cycle.clock[0] += timedelta(seconds=308)
    morning = await cycle.turns.sync(cycle.game.id)
    assert morning.journal[-1].victim_id is None
    assert morning.journal[-1].detention_outcome == "released"
    assert len(morning.crimes) == 1 and morning.status == "active"
    cycle.clock[0] += timedelta(seconds=308)
    ended = await cycle.turns.sync(cycle.game.id)
    assert ended.status == "lost" and ended.phase == "finished"
    assert (await storage.games.get(cycle.game.id)).status == "lost"
    assert ended.journal[-1].victim_id == "escobar"


async def test_offline_catchup_uses_original_deadlines_and_terminates(cycle, storage):
    cycle.clock[0] += timedelta(days=30)
    case = await cycle.turns.sync(cycle.game.id)
    assert case.status == "lost" and case.phase == "finished"
    assert case.day == 5  # Quatro vítimas entre os sete moradores; Brás Cubas não entra.
    killed = await events(storage, cycle, "character.killed")
    assert len(killed) == len({record["data"]["victim_id"] for record in killed}) == 4
    assert case.phase_ends_at == cycle.game.created_at + timedelta(seconds=4 * 308)
    assert len(case.journal) == 5
    assert await cycle.turns.sync(cycle.game.id) == case


async def test_concurrent_clients_never_duplicate_night(cycle, storage):
    cycle.clock[0] += timedelta(seconds=308)
    results = await asyncio.gather(*(cycle.turns.sync(cycle.game.id) for _ in range(2)), return_exceptions=True)
    assert any(not isinstance(result, Exception) for result in results)
    assert all(not isinstance(result, Exception) or isinstance(result, ConflictError) for result in results)
    assert len(await events(storage, cycle, "character.killed")) == 1
    assert len(await events(storage, cycle, "journal.published")) == 1


async def test_bad_events_key_blocks_all_night_state_changes(cycle, storage):
    before = {suffix: await storage.client.get(f"{cycle.key}:{suffix}")
              for suffix in ("state", "world", "investigation")}
    await storage.client.delete(f"{cycle.key}:events")
    await storage.client.set(f"{cycle.key}:events", "invalid-list")
    cycle.clock[0] += timedelta(seconds=308)
    with pytest.raises(StorageUnavailableError):
        await cycle.turns.sync(cycle.game.id)
    assert {suffix: await storage.client.get(f"{cycle.key}:{suffix}") for suffix in before} == before


async def test_legacy_cycle_starts_now_without_reroll_and_bootstraps_once(cycle, storage):
    await storage.client.delete(f"{cycle.key}:investigation")
    cycle.clock[0] += timedelta(days=100)
    case = await cycle.turns.sync(cycle.game.id)
    assert case.day == 1 and case.phase == "day"
    assert case.phase_ends_at == cycle.clock[0] + timedelta(seconds=300)
    assert await storage.games.get(cycle.game.id) == cycle.game
    assert len(await events(storage, cycle, "investigation.initialized")) == 1
    assert await cycle.turns.sync(cycle.game.id) == case
    assert len(await events(storage, cycle, "investigation.initialized")) == 1


async def test_dialogue_deadline_rejects_without_mutating_or_acquiring_nested_gate(cycle, storage):
    async with cycle.gate.hold(cycle.game.id):
        await cycle.turns.assert_dialogue_open(cycle.game.id)
        cycle.clock[0] += timedelta(seconds=300)
        with pytest.raises(ConflictError):
            await cycle.turns.assert_dialogue_open(cycle.game.id)
    assert (await cycle.turns._repository.get(cycle.game.id)).phase == "day"
    assert not await events(storage, cycle, "night.started")


async def test_act_sets_revision_and_events_and_unchanged_action_does_not_write(cycle, storage):
    initial = await cycle.turns.sync(cycle.game.id)
    assert await cycle.turns.act(cycle.game.id, lambda state, *_: CaseTransition(state=state)) == initial
    detained = await detain(cycle, "capitu")
    assert detained.revision == initial.revision + 1
    assert len(await events(storage, cycle, "suspect.detained")) == 1
    with pytest.raises(ValueError):
        await cycle.turns.act(cycle.game.id, lambda state, *_: CaseTransition(
            state=state.model_copy(update={"day": 99})))
    assert await cycle.turns.sync(cycle.game.id) == detained


async def test_restore_new_service_preserves_clock_state_and_roles(cycle, storage, catalog):
    cycle.clock[0] += timedelta(seconds=308)
    case = await cycle.turns.sync(cycle.game.id)
    restored = TurnService(storage.client, storage.prefix, storage.games, catalog, cycle.world, cycle.gate,
                           clock=lambda: cycle.clock[0])
    assert await restored.sync(cycle.game.id) == case
    with pytest.raises(NotFoundError):
        await restored.sync(uuid4())


async def test_corrupt_cycle_identity_is_sanitized(cycle, storage):
    case = await cycle.turns.sync(cycle.game.id)
    corrupt = case.model_copy(update={"game_id": uuid4()})
    await storage.client.set(f"{cycle.key}:investigation", corrupt.model_dump_json())
    with pytest.raises(StorageUnavailableError):
        await cycle.turns.sync(cycle.game.id)


async def test_stale_world_prevents_partial_case_commit(cycle, storage):
    state = await cycle.turns.sync(cycle.game.id)
    world = await cycle.world.get(cycle.game.id)
    newer_world = world.model_copy(update={"revision": world.revision + 1})
    await cycle.world.save(newer_world, expected_revision=world.revision)
    before = await storage.client.get(f"{cycle.key}:investigation")
    with pytest.raises(ConflictError):
        await cycle.turns._repository.commit(
            previous=state, state=state.model_copy(update={"revision": state.revision + 1}),
            previous_game=cycle.game, game=cycle.game, previous_world=world, world=world,
            events=(CaseEvent(type="must.not.exist", data={}),), occurred_at=cycle.clock[0],
        )
    assert await storage.client.get(f"{cycle.key}:investigation") == before
    assert await cycle.world.get(cycle.game.id) == newer_world
    assert not await events(storage, cycle, "must.not.exist")


async def test_cycle_transaction_refuses_role_reassignment(cycle):
    state = await cycle.turns.sync(cycle.game.id)
    world = await cycle.world.get(cycle.game.id)
    tampered = cycle.game.model_copy(update={"characters": tuple(
        member.model_copy(update={"role": "werewolf" if member.character_id == "capitu" else "civil"})
        for member in cycle.game.characters)})
    with pytest.raises(ValueError):
        await cycle.turns._repository.commit(
            previous=state, state=state.model_copy(update={"revision": state.revision + 1}),
            previous_game=cycle.game, game=tampered, previous_world=world, world=world,
            events=(), occurred_at=cycle.clock[0],
        )


async def test_restart_during_night_resumes_same_deadline(cycle, storage, catalog):
    cycle.clock[0] += timedelta(seconds=300)
    night = await cycle.turns.sync(cycle.game.id)
    restored = TurnService(storage.client, storage.prefix, storage.games, catalog, cycle.world, cycle.gate,
                           clock=lambda: cycle.clock[0])
    cycle.clock[0] += timedelta(seconds=7)
    assert await restored.sync(cycle.game.id) == night
    cycle.clock[0] += timedelta(seconds=1)
    morning = await restored.sync(cycle.game.id)
    assert morning.day == 2 and morning.phase == "day"
    assert morning.phase_ends_at == cycle.game.created_at + timedelta(seconds=608)
    assert len(await events(storage, cycle, "character.killed")) == 1


async def test_unexpired_reads_do_not_require_player_gate(cycle, storage):
    initial = await cycle.turns.sync(cycle.game.id)
    before = await storage.client.get(f"{cycle.key}:investigation")
    async with cycle.gate.hold(cycle.game.id):
        assert await cycle.turns.sync(cycle.game.id) == initial
        results = await asyncio.gather(*(cycle.turns.sync(cycle.game.id) for _ in range(3)))
        assert all(result == initial for result in results)
    assert await storage.client.get(f"{cycle.key}:investigation") == before
    assert len(await events(storage, cycle)) == 3


async def test_due_reads_still_require_gate_and_do_not_resolve_around_pending_action(cycle, storage):
    cycle.clock[0] += timedelta(seconds=300)
    async with cycle.gate.hold(cycle.game.id):
        with pytest.raises(ConflictError):
            await cycle.turns.sync(cycle.game.id)
    assert not await events(storage, cycle, "night.started")
    assert (await cycle.turns.sync(cycle.game.id)).phase == "night"


async def test_fast_read_detects_inconsistent_status_and_wrong_key_type(cycle, storage):
    game = cycle.game.model_copy(update={"status": "won"})
    await storage.client.set(f"{cycle.key}:state", game.model_dump_json())
    with pytest.raises(StorageUnavailableError):
        await cycle.turns.sync(cycle.game.id)
    await storage.client.set(f"{cycle.key}:state", cycle.game.model_dump_json())
    await storage.client.delete(f"{cycle.key}:investigation")
    await storage.client.rpush(f"{cycle.key}:investigation", "not-a-json-string")
    with pytest.raises(StorageUnavailableError):
        await cycle.turns.sync(cycle.game.id)
    assert await storage.client.type(f"{cycle.key}:investigation") == "list"


async def test_terminal_reads_do_not_require_player_gate(cycle):
    await detain(cycle, "bentinho")
    cycle.clock[0] += timedelta(seconds=308)
    terminal = await cycle.turns.sync(cycle.game.id)
    async with cycle.gate.hold(cycle.game.id):
        assert await cycle.turns.sync(cycle.game.id) == terminal


async def test_victory_editorial_is_persisted_once(cycle, storage):
    from src.modules.session_master.service import SessionMasterService
    from src.modules.session_master.editorial import SIGNATURE
    calls = []
    master = SessionMasterService(cycle.turns, storage.games, None)
    async def editor(state, game):
        calls.append(state.ending_method)
        return await master.publish_victory(state, game)
    cycle.turns._victory_editor = editor
    await cycle.turns.sync(cycle.game.id)
    await detain(cycle, 'bentinho')
    cycle.clock[0] += timedelta(seconds=308)
    ended = await cycle.turns.sync(cycle.game.id)
    assert ended.status == 'won'
    assert ended.journal[-1].body.endswith(SIGNATURE)
    assert 'Bentinho era o lobisomem' in ended.journal[-1].body
    assert (await cycle.turns.sync(cycle.game.id)).journal == ended.journal
    assert calls == ['detention']
    persisted = await cycle.turns._repository.get(cycle.game.id)
    assert persisted.journal == ended.journal
