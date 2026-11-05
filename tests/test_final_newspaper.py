import pytest
from datetime import timedelta
from test_turns import cycle,detain
from test_interrogations import inquiry,dossier

pytestmark=pytest.mark.anyio

async def test_detention_victory_has_named_final_newspaper(cycle):
    await detain(cycle,'bentinho')
    cycle.clock[0]+=timedelta(seconds=308)
    state=await cycle.turns.sync(cycle.game.id)
    edition=state.journal[-1]
    assert state.status=='won' and edition.illustration=='victory'
    assert 'Floriano' in edition.headline and 'Bentinho' in edition.body
    assert 'expulso' in edition.body

async def test_assembly_victory_persists_extraordinary_edition(inquiry):
    state,game,evidence,testimony=await dossier(inquiry)
    await inquiry.storage.client.set(inquiry.key+':investigation',state.model_dump_json())
    result=await inquiry.service.assemble(game.id,'capitu',evidence,testimony)
    assert result.journal[-1].illustration=='victory'
    assert 'Floriano' in result.journal[-1].headline and 'Capitu' in result.journal[-1].body
    assert 'expulsa da cidade' in result.journal[-1].body
    restored=await inquiry.turns.sync(game.id)
    assert restored.journal[-1].body==result.journal[-1].body


async def test_four_werewolf_cast_deaths_end_case_with_defeat_newspaper(cycle, storage):
    from memorias_licantropicas.modules.investigation.service import InvestigationService

    cycle.clock[0] += timedelta(seconds=3 * 308)
    before = await cycle.turns.sync(cycle.game.id)
    assert before.status == 'active' and len(before.crimes) == 4
    cycle.clock[0] += timedelta(seconds=308)
    ended = await cycle.turns.sync(cycle.game.id)
    game = await storage.games.get(cycle.game.id)
    assert ended.status == game.status == 'lost' and ended.phase == 'finished'
    assert sum(not member.alive for member in game.characters) == 4
    assert sum(member.alive for member in game.characters) == 3
    edition = ended.journal[-1]
    assert edition.headline == 'Floriano não chegou a tempo: a besta-fera venceu'
    assert 'Quatro dos sete moradores' in edition.body
    assert 'Não restam civis' not in edition.body
    public = await InvestigationService(cycle.turns, cycle.turns._characters).public(ended)
    assert public.ending.result == 'lost'
    assert 'A besta-fera venceu' in public.ending.message
    cycle.clock[0] += timedelta(days=1)
    assert await cycle.turns.sync(cycle.game.id) == ended


async def test_detaining_wolf_before_fourth_victim_still_wins(cycle):
    cycle.clock[0] += timedelta(seconds=3 * 308)
    assert (await cycle.turns.sync(cycle.game.id)).status == 'active'
    await detain(cycle, 'bentinho')
    cycle.clock[0] += timedelta(seconds=308)
    assert (await cycle.turns.sync(cycle.game.id)).status == 'won'


async def test_defeat_count_excludes_human_murders_opening_and_duplicate_victims(cycle):
    from memorias_licantropicas.modules.investigation.rules import werewolf_cast_victims

    opening = (await cycle.turns.sync(cycle.game.id)).crimes[0]
    wolf_crime = opening.model_copy(update={'victim_id': 'capitu'})
    human_crime = opening.model_copy(update={'victim_id': 'escobar', 'cause': 'civil', 'killer_id': 'rubiao'})
    wrong_killer = opening.model_copy(update={'victim_id': 'virgilia', 'killer_id': 'rubiao'})
    assert werewolf_cast_victims((opening, wolf_crime, wolf_crime, human_crime, wrong_killer),
        {member.character_id for member in cycle.game.characters}, 'bentinho') == {'capitu'}
