from uuid import uuid4
import pytest
from test_interrogations import inquiry,dossier
from test_session_master_v2 import pair,NOW
from memorias_licantropicas.modules.session_master.service import local_assessment
from memorias_licantropicas.modules.session_master.rules import dialogue_transition
from memorias_licantropicas.modules.agents.support import is_alibi_question
from memorias_licantropicas.modules.investigation.rules import make_initial_investigation

pytestmark=pytest.mark.anyio

@pytest.mark.parametrize('question',[
    'Com quem devo falar para entender o caso?',
    'Onde posso procurar uma pista?',
    'Quem pode reconhecer esse objeto?',
    'O que devo perguntar para Capitu?',
])
async def test_investigative_guidance_does_not_register_an_alibi(question):
    result=local_assessment(question,'Capitu pode contar sobre sua amizade com Escobar.',1)
    assert result.kind!='alibi' and not is_alibi_question(question)

@pytest.mark.parametrize('question',[
    'Onde estava na noite de ontem?', 'Com quem você estava?',
    'O que fazia na noite do crime?', 'Onde o senhor esteve naquele dia?',
])
async def test_real_whereabouts_question_still_registers_an_alibi(question):
    assert local_assessment(question,'Eu estava no Café do Largo.',1).kind=='alibi'

async def test_unspoken_observations_are_not_promoted_to_public_proof(game):
    state=make_initial_investigation(game,NOW)
    incoming,outgoing=pair(text='Não me lembro de onde estava.',incoming='Onde estava naquela noite?')
    assessment=local_assessment(incoming.content,outgoing.content,1)
    result=dialogue_transition(state,game,'bentinho',uuid4(),incoming,outgoing,assessment,NOW)
    record=result.state.interrogations[-1]
    assert record.location_id is None and record.observations==() and record.companion_ids==()

async def test_inspection_public_projection_awards_once_without_private_truth(inquiry):
    state,game,evidence_ids,_=await dossier(inquiry)
    await inquiry.storage.client.set(inquiry.key+':investigation',state.model_dump_json())
    from memorias_licantropicas.modules.investigation.catalog import ITEMS_BY_ID
    item=next(e for c in state.crimes for e in c.evidence if ITEMS_BY_ID[e.item_id].kind=='unique')
    result=await inquiry.service.inspect(game.id,item.id)
    assert [a.id for a in result.achievements]==['personal_trace']
    assert result.achievement_total==7
    serialized=result.model_dump_json()
    for forbidden in ('crime_link_verified','deposited_by','source_record_ids'):
        assert forbidden not in serialized
    inspected=next(e for e in result.inventory if e.id==item.id)
    assert inspected.examined and inspected.inspection_text
    again=await inquiry.service.inspect(game.id,item.id)
    assert again.achievements==result.achievements and again.revision==result.revision
