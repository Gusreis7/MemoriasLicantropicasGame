import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.contracts.errors import ConflictError, StorageUnavailableError
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


async def test_due_reads_still_require_gate_and_do_not_resolve_around_pending_action(cycle, storage):
    cycle.clock[0] += timedelta(seconds=300)
    async with cycle.gate.hold(cycle.game.id):
        with pytest.raises(ConflictError):
            await cycle.turns.sync(cycle.game.id)
    assert not await events(storage, cycle, "night.started")
    assert (await cycle.turns.sync(cycle.game.id)).phase == "night"


async def _accepted_detention(cycle, suspect):
    from src.contracts.investigation import Accusation
    def transition(state, _game, _world):
        record = Accusation(id=uuid4(), day=state.day, suspect_id=suspect,
            evidence_ids=(), testimony_ids=(), accepted=True, reason='provas confirmadas', created_at=cycle.clock[0])
        return CaseTransition(state=state.model_copy(update={'detained_npc_id': suspect,
            'accusations': (*state.accusations, record)}),
            events=(CaseEvent(type='suspect.detained', data={'suspect_id': suspect}),))
    return await cycle.turns.act(cycle.game.id, transition, start_night_on_detention=True)


async def _deferred_editor(cycle, storage):
    import asyncio
    from native_fixtures import respond_to_tools
    from src.modules.session_master.service import SessionMasterService
    started, released, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()
    class LLM:
        calls = 0
        async def complete(self, messages, *, tools=(), tool_choice=None):
            self.calls += 1
            started.set()
            try:
                await released.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return respond_to_tools({'opinion': 'O esforço de Floriano merece o reconhecimento dos moradores. Que esta vitória nos ensine a cuidar da memória das vítimas e a exigir justiça.'}, tools, tool_choice)
    llm = LLM()
    master = SessionMasterService(cycle.turns, storage.games, None, llm, storage.client, storage.prefix)
    cycle.turns._victory_editor = master.publish_victory
    cycle.turns._detention_editor = master.prepare_detention_editorial
    return SimpleNamespace(master=master, llm=llm, started=started, released=released, cancelled=cancelled)


async def test_editorial_prepares_during_suspense_and_publishes_only_after_night(cycle, storage):
    import asyncio
    editor = await _deferred_editor(cycle, storage)
    try:
        night = await asyncio.wait_for(_accepted_detention(cycle, 'bentinho'), .25)
        await asyncio.wait_for(editor.started.wait(), .25)
        assert night.phase == 'night' and night.status == 'active'
        assert 'Bentinho era o lobisomem' not in night.journal[-1].body
        assert (await cycle.turns._repository.get(cycle.game.id)).journal == night.journal
        # A pending model has not retained the player's gate.
        async with cycle.gate.hold(cycle.game.id):
            pass
        task = editor.master._editorial_tasks[cycle.game.id]
        editor.released.set()
        await asyncio.wait_for(task, .5)
        private = await storage.client.get(editor.master._editorial_key(cycle.game.id))
        assert private is not None
        assert (await cycle.turns.sync(cycle.game.id)).journal == night.journal
        # A different process can consume the ready cache after restart.
        from src.modules.session_master.service import SessionMasterService
        restored = SessionMasterService(cycle.turns, storage.games, None, redis=storage.client, prefix=storage.prefix)
        cycle.turns._victory_editor = restored.publish_victory
        cycle.clock[0] += timedelta(seconds=8)
        ended = await asyncio.wait_for(cycle.turns.sync(cycle.game.id), .25)
        assert ended.status == 'won'
        assert 'O esforço de Floriano' in ended.journal[-1].body
        assert 'Bentinho era o lobisomem' in ended.journal[-1].body
        assert editor.llm.calls == 1
        # Cache cannot be reused for a different canonical outcome/day.
        other = await restored.publish_victory(ended.model_copy(update={'day': ended.day + 1}), cycle.game)
        assert 'O esforço de Floriano' not in other.journal[-1].body
        changed_crime = ended.crimes[0].model_copy(update={'victim_id': 'escobar', 'killer_id': 'bentinho', 'cause': 'werewolf'})
        changed = await restored.publish_victory(ended.model_copy(update={'crimes': (changed_crime, *ended.crimes[1:])}), cycle.game)
        assert 'O esforço de Floriano' not in changed.journal[-1].body
        await restored.aclose()
    finally:
        await editor.master.aclose()


async def test_pending_editorial_never_delays_result_and_shutdown_cancels_provider(cycle, storage):
    import asyncio
    editor = await _deferred_editor(cycle, storage)
    await _accepted_detention(cycle, 'bentinho')
    await asyncio.wait_for(editor.started.wait(), .25)
    cycle.clock[0] += timedelta(seconds=8)
    ended = await asyncio.wait_for(cycle.turns.sync(cycle.game.id), .25)
    assert ended.status == 'won' and 'Bentinho era o lobisomem' in ended.journal[-1].body
    assert 'O esforço de Floriano' not in ended.journal[-1].body
    await asyncio.sleep(0)
    assert editor.cancelled.is_set()
    await editor.master.aclose()
    assert editor.cancelled.is_set() and not editor.master._editorial_tasks


@pytest.mark.parametrize('changed', ['innocent', 'revision'])
async def test_editorial_rejects_innocent_and_stale_detention(cycle, storage, changed):
    import asyncio
    editor = await _deferred_editor(cycle, storage)
    try:
        night = await _accepted_detention(cycle, 'capitu' if changed == 'innocent' else 'bentinho')
        if changed == 'innocent':
            task = editor.master._editorial_tasks.get(cycle.game.id)
            if task:
                await task
            assert editor.llm.calls == 0
        else:
            await asyncio.wait_for(editor.started.wait(), .25)
            task = editor.master._editorial_tasks[cycle.game.id]
            await storage.client.set(f'{cycle.key}:investigation', night.model_copy(update={'revision': night.revision + 1}).model_dump_json())
            editor.released.set()
            await task
        assert await storage.client.get(editor.master._editorial_key(cycle.game.id)) is None
    finally:
        await editor.master.aclose()


async def test_editorial_does_not_start_provider_after_waiting_past_night_deadline(cycle, storage):
    editor = await _deferred_editor(cycle, storage)
    await editor.master._editorial_slots.acquire()
    await editor.master._editorial_slots.acquire()
    try:
        await _accepted_detention(cycle, 'bentinho')
        task = editor.master._editorial_tasks[cycle.game.id]
        cycle.clock[0] += timedelta(seconds=8)
        editor.master._editorial_slots.release()
        await task
        assert editor.llm.calls == 0
        assert await storage.client.get(editor.master._editorial_key(cycle.game.id)) is None
    finally:
        editor.master._editorial_slots.release()
        await editor.master.aclose()


async def test_restart_with_pending_editorial_uses_immediate_fallback(cycle, storage):
    import asyncio
    from src.modules.session_master.service import SessionMasterService
    editor = await _deferred_editor(cycle, storage)
    await _accepted_detention(cycle, 'bentinho')
    await asyncio.wait_for(editor.started.wait(), .25)
    await editor.master.aclose()
    restored = SessionMasterService(cycle.turns, storage.games, None, redis=storage.client, prefix=storage.prefix)
    cycle.turns._victory_editor = restored.publish_victory
    cycle.clock[0] += timedelta(seconds=8)
    ended = await asyncio.wait_for(cycle.turns.sync(cycle.game.id), .25)
    assert ended.status == 'won' and 'O esforço de Floriano' not in ended.journal[-1].body
    await restored.aclose()
