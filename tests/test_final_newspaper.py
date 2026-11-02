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
