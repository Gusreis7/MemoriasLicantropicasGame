"""Deterministic post-freeze corrections; no provider calls or benchmark changes."""
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from memorias_licantropicas.contracts.model import ConversationMessage, GameCharacter, LLMResponse
from memorias_licantropicas.modules.agents.support import dialogue_supports
import json
from memorias_licantropicas.modules.achievements.rules import award, discoveries_in_reply
from memorias_licantropicas.modules.knowledge.seeds import TOPICS
from memorias_licantropicas.modules.investigation.rules import make_initial_investigation
from memorias_licantropicas.modules.session_master.rules import dialogue_transition
from memorias_licantropicas.modules.session_master.service import DialogueAssessment

pytestmark=pytest.mark.anyio
NOW=datetime(2026,11,2,12,tzinfo=UTC)


def observations(topic, origin='authored'):
    text=next(t[3] for t in TOPICS if t[0]==topic)
    return {'memoria_social':{'memorias_relevantes':[{'claim_id':topic,'conteudo':text,
        'origem':origin,'quem_falou':'virgilia','compartilhavel':True,'tipo':'report'}]}}


@pytest.mark.parametrize('npc,topic,first,other',[
    ('bentinho','seminario','Escobar e eu estudamos','Escobar'),
    ('escobar','seminario','Bentinho e eu estudamos','Bentinho'),
    ('bentinho','tratamento','Eu faço acompanhamento','Bacamarte'),
    ('bacamarte','tratamento','Eu acompanho Bentinho','Bentinho'),
    ('florenca','causa-florenca','internado meu pai','Bacamarte'),
    ('rubiao','rubiao-insistente','minha insistência',None),
])
async def test_persona_keeps_generated_voice_and_canonical_prompt_facts(catalog,harness,storage,game,llm,npc,topic,first,other):
    profile=await catalog.get(npc);obs=observations(topic)
    original=obs['memoria_social']['memorias_relevantes'][0]['conteudo']
    if npc not in {member.character_id for member in game.characters}:
        game=game.model_copy(update={'characters':(*game.characters,GameCharacter(character_id=npc,role='civil'))})
    await storage.games.create(game)
    async def context(*args):return obs
    harness._context_provider=context
    answer=first+'.'
    async def complete(messages):
        llm.calls.append(messages)
        return LLMResponse(content=json.dumps({'fala':answer}),model='voice-fixture')
    llm.complete=complete
    reply=await harness.respond(game.id,npc,uuid4(),'player','O que sabe?')
    assert reply.message.content==answer and reply.model=='voice-fixture'
    projected=json.loads(llm.calls[0][0].content.split('Ficha privada:\n',1)[1])
    supports=projected['observacoes_autorizadas']['apoios_de_conversa']
    assert supports[0]['statement']==original
    assert profile.name not in supports[0]['lead']
    if other:assert other in supports[0]['lead']


async def test_forwarded_and_recorded_testimony_keep_source_in_persona_prompt(catalog,harness,game):
    profile=await catalog.get('escobar');obs=observations('seminario','heard')
    original=obs['memoria_social']['memorias_relevantes'][0]['conteudo']
    supports=dialogue_supports(profile,obs,'seminário')
    assert supports[0]['statement']==f'Ouvi de Virgília: {original}'
    obs={'seus_depoimentos_registrados':[{'fala':original,'evidence_id':'test'}]}
    supports=dialogue_supports(profile,obs,'seminário')
    assert supports[0]['statement']==original


@pytest.mark.parametrize('npc,text,expected',[
    ('escobar','Bentinho e eu estudamos juntos no seminário.',True),
    ('bentinho','Escobar e eu estudamos juntos no seminário.',True),
    ('rubiao','Bentinho e eu estudamos juntos no seminário.',False),
    ('capitu','Escobar e eu estudamos juntos no seminário.',False),
    ('escobar','Bentinho e eu não estudamos juntos no seminário.',False),
    ('escobar','Dizem que Bentinho e eu estudamos juntos no seminário.',False),
    ('escobar','Ele disse: “Bentinho e eu estudamos juntos no seminário”.',False),
    ('escobar','Se Bentinho e eu estudamos juntos no seminário, não lembro.',False),
    ('escobar','Talvez Bentinho e eu estudamos juntos no seminário.',False),
    ('escobar','Bentinho e eu estudamos juntos no seminário?',False),
])
async def test_seminary_requires_the_actual_emitter_and_assertion(npc,text,expected):
    assert bool(discoveries_in_reply(npc,text,('seminary_bond',))) is expected


@pytest.mark.parametrize('old_npc,authorized,expected',[
    ('rubiao',True,False),('escobar',False,False),('escobar',True,True),
])
async def test_historical_first_person_keeps_original_emitter(game,old_npc,authorized,expected):
    state=make_initial_investigation(game,NOW)
    state=state.model_copy(update={'dialogue_events':({'npc_id':old_npc,
        'outgoing':'Bentinho e eu estudamos juntos no seminário.',
        'narrative_authorized':authorized,'assessment':{'eligible_discovery_ids':['seminary_bond']}},)})
    incoming=ConversationMessage(id=uuid4(),sender_id='player',content='Escobar e Bentinho estudaram no seminário?',created_at=NOW)
    outgoing=ConversationMessage(id=uuid4(),sender_id='escobar',content='Ainda estou aqui.',created_at=NOW,narrative_authorized=True)
    result=dialogue_transition(state,game,'escobar',uuid4(),incoming,outgoing,
        DialogueAssessment(eligible_discovery_ids=('seminary_bond',)),NOW)
    assert bool(result.state.achievements) is expected


@pytest.mark.parametrize('npc,text,identifier',[
    ('virgilia','Capitu e Bentinho são casados. Capitu e Escobar são amigos.','marriage_triangle'),
    ('escobar','Bentinho e eu estudamos juntos no seminário.','seminary_bond'),
    ('capitu','Bentinho faz acompanhamento com Bacamarte, mas não toma os remédios.','treatment_bentinho'),
    ('florenca','Bacamarte internou meu pai.','florenca_father'),
    ('capitu','Quero me separar de Bentinho.','capitu_separation'),
    ('escobar','Amo Bentinho além da amizade.','escobar_affection'),
])
async def test_six_dialogue_discoveries_remain_reachable_only_when_authorized(npc,text,identifier):
    assert discoveries_in_reply(npc,text,(identifier,))==(identifier,)
    assert discoveries_in_reply(npc,text,())==()


async def test_seventh_discovery_is_idempotent_examination_award(game):
    state=make_initial_investigation(game,NOW)
    updated=award(state,'personal_trace',NOW,source_message_id=state.crimes[0].evidence[0].id)
    assert [a.id for a in updated.achievements]==['personal_trace']
    assert award(updated,'personal_trace',NOW)==updated


@pytest.mark.parametrize('npc,text,identifier',[
    ('virgilia','Bacamarte internou meu pai.','florenca_father'),
    ('capitu','Bentinho não faz acompanhamento com Bacamarte nem toma remédios.','treatment_bentinho'),
    ('capitu','Talvez Bentinho não toma os remédios de Bacamarte.','treatment_bentinho'),
    ('capitu','Ele disse: “Bentinho não toma os remédios de Bacamarte”.','treatment_bentinho'),
])
async def test_resistance_exception_does_not_infer_unrelated_or_denied_facts(npc,text,identifier):
    assert discoveries_in_reply(npc,text,(identifier,))==()
