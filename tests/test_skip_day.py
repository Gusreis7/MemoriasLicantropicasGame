"""Avanço manual usa as mesmas regras da noite, com persistência atômica."""
from datetime import timedelta

import pytest

from test_turns import cycle, detain, events
from test_case_integration import seed_case
from test_interrogations import inquiry
from memorias_licantropicas.contracts.errors import ConflictError, StorageUnavailableError

pytestmark = pytest.mark.anyio


async def test_skip_resolves_one_night_and_resets_morning_clock(cycle, storage):
    before = await cycle.turns.sync(cycle.game.id)
    cycle.clock[0] += timedelta(seconds=100)
    after = await cycle.turns.skip_day(cycle.game.id, before.day)
    assert after.day == 2 and after.phase == 'day' and after.status == 'active'
    assert after.revision == before.revision + 1
    assert after.phase_ends_at == cycle.clock[0] + timedelta(seconds=300)
    assert len(after.crimes) == 2 and len(after.journal) == 2
    assert after.journal[-1].victim_id == after.crimes[-1].victim_id
    assert {record.period for record in after.activity_records if record.day == 1} == {'day', 'night'}
    world = await cycle.world.get(cycle.game.id)
    assert world.player.location_id == 'praca_verde' and world.player.x == 160
    assert world.player.direction == 'idle' and world.player.last_updated_at == cycle.clock[0]
    assert len(await events(storage, cycle, 'night.started')) == 1
    assert len(await events(storage, cycle, 'journal.published')) == 1
    with pytest.raises(ConflictError):
        await cycle.turns.skip_day(cycle.game.id, before.day)
    assert await cycle.turns.sync(cycle.game.id) == after


async def test_skip_can_end_in_fourth_victim_defeat(cycle, storage):
    for day in range(1, 5):
        state = await cycle.turns.skip_day(cycle.game.id, day)
    assert state.status == 'lost' and state.phase == 'finished' and state.day == 5
    assert 'besta-fera venceu' in state.journal[-1].headline
    assert (await storage.games.get(cycle.game.id)).status == 'lost'
    with pytest.raises(ConflictError):
        await cycle.turns.skip_day(cycle.game.id, 5)


@pytest.mark.parametrize('suspect', ['bentinho', 'escobar'])
async def test_skip_preserves_detention_rules(cycle, suspect):
    await detain(cycle, suspect)
    state = await cycle.turns.skip_day(cycle.game.id, 1)
    if suspect == 'bentinho':
        assert state.status == 'won' and len(state.crimes) == 1
        assert state.journal[-1].detention_outcome == 'transformed'
    else:
        assert state.status == 'active' and state.detained_npc_id is None
        assert state.journal[-1].detention_outcome == 'released'
        assert state.crimes[-1].victim_id != suspect


async def test_skip_does_not_bypass_night_or_player_gate(cycle):
    async with cycle.gate.hold(cycle.game.id):
        with pytest.raises(ConflictError):
            await cycle.turns.skip_day(cycle.game.id, 1)
    cycle.clock[0] += timedelta(seconds=300)
    with pytest.raises(ConflictError):
        await cycle.turns.skip_day(cycle.game.id, 1)
    assert (await cycle.turns.sync(cycle.game.id)).phase == 'night'


async def test_skip_does_not_bypass_assembly(inquiry):
    await inquiry.service.open_assembly(inquiry.game.id, 'capitu', speech='Vamos ouvir as versões.')
    with pytest.raises(ConflictError):
        await inquiry.turns.skip_day(inquiry.game.id, 1)


async def test_skip_commit_failure_does_not_partially_advance(cycle, storage):
    before = {suffix: await storage.client.get(f'{cycle.key}:{suffix}')
              for suffix in ('state', 'world', 'investigation')}
    await storage.client.delete(f'{cycle.key}:events')
    await storage.client.set(f'{cycle.key}:events', 'invalid-list')
    with pytest.raises(StorageUnavailableError):
        await cycle.turns.skip_day(cycle.game.id, 1)
    assert {suffix: await storage.client.get(f'{cycle.key}:{suffix}') for suffix in before} == before


async def test_skip_rest_validates_day_and_rejects_repeat(api_client, storage, catalog, single_wolf_attack):
    game, clock, base, original = await seed_case(api_client, storage, catalog)
    for body in ({}, {'day': 0}, {'day': '1'}, {'day': 1, 'seconds': 9999}):
        assert (await api_client.post(f'{base}/investigation/skip-day', json=body)).status_code == 422
    response = await api_client.post(f'{base}/investigation/skip-day', json={'day': 1})
    assert response.status_code == 200
    state = response.json()
    assert state['day'] == 2 and state['seconds_remaining'] == 300
    assert state['ending'] is None and 'killer_id' not in response.text
    assert (await api_client.post(f'{base}/investigation/skip-day', json={'day': 1})).status_code == 409
    assert (await api_client.get(f'{base}/investigation')).json() == state
