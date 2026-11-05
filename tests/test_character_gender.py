from datetime import timedelta
from uuid import uuid4

import pytest

from src.contracts.investigation import CaseTransition
from src.modules.characters.service import public_character
from test_turns import cycle

pytestmark = pytest.mark.anyio
CAST = ('bentinho', 'capitu', 'escobar', 'rubiao', 'virgilia', 'florenca', 'bacamarte')
FEMININE = {'capitu', 'virgilia', 'florenca'}


@pytest.mark.parametrize('person_id', CAST)
async def test_every_character_transforms_in_custody_with_correct_named_ending(cycle, storage, catalog, person_id):
    profile = await catalog.get(person_id)
    public = public_character(profile)
    assert public.grammatical_gender == ('feminine' if person_id in FEMININE else 'masculine')
    game = cycle.game.model_copy(update={'id': uuid4(), 'characters': tuple(
        member.model_copy(update={'role': 'werewolf' if member.character_id == person_id else 'civil'})
        for member in cycle.game.characters)})
    await storage.games.create(game)
    await cycle.turns.act(game.id, lambda state, *_: CaseTransition(
        state=state.model_copy(update={'detained_npc_id': person_id})))
    cycle.clock[0] += timedelta(seconds=308)
    state = await cycle.turns.sync(game.id)
    assert state.status == 'won'
    assert state.journal[-1].detention_outcome == 'transformed'
    assert f'{profile.name} se transformou na cela' in state.journal[-1].body
    assert f"{profile.name} foi {'expulsa' if person_id in FEMININE else 'expulso'}" in state.journal[-1].body


@pytest.mark.parametrize('person_id', CAST)
async def test_every_innocent_character_is_released_with_correct_agreement(cycle, storage, catalog, person_id):
    wolf = 'capitu' if person_id == 'bentinho' else 'bentinho'
    game = cycle.game.model_copy(update={'id': uuid4(), 'characters': tuple(
        member.model_copy(update={'role': 'werewolf' if member.character_id == wolf else 'civil'})
        for member in cycle.game.characters)})
    await storage.games.create(game)
    await cycle.turns.act(game.id, lambda state, *_: CaseTransition(
        state=state.model_copy(update={'detained_npc_id': person_id})))
    cycle.clock[0] += timedelta(seconds=308)
    state = await cycle.turns.sync(game.id)
    profile = await catalog.get(person_id)
    assert state.status == 'active' and state.detained_npc_id is None
    assert state.journal[-1].detention_outcome == 'released'
    assert f"{profile.name} não se transformou e foi {'solta' if person_id in FEMININE else 'solto'}" in state.journal[-1].body
    assert next(member for member in (await storage.games.get(game.id)).characters if member.character_id == person_id).alive
