"""Regressões das conversas de Capitu e Rubião em 04/11/2026."""
from uuid import uuid4
from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock
import json

import pytest

from memorias_licantropicas.contracts.model import ConversationMessage, GameCharacter, LLMResponse
from memorias_licantropicas.modules.agents.support import dialogue_supports, historical_dialogue_content, is_courtesy_reply
from memorias_licantropicas.modules.session_master.service import SessionMasterService

pytestmark = pytest.mark.anyio


def observations():
    return {'dia': 1, 'memoria_social': {'memorias_relevantes': [
        {'claim_id': 'marriage', 'origem': 'authored', 'quem_falou': 'capitu',
         'conteudo': 'Capitu e Bentinho são casados; o ciúme dele tem provocado discussões.', 'tipo': 'report'},
        {'claim_id': 'treatment', 'origem': 'authored', 'quem_falou': 'capitu',
         'conteudo': 'Bentinho faz acompanhamento com Bacamarte, mas resiste às consultas e à medicação.', 'tipo': 'report'},
        {'claim_id': 'player-item', 'origem': 'heard', 'quem_falou': 'player', 'tipo': 'report',
         'conteudo': 'Floriano disse a Rubião: «Mostro-lhe Lenço de algodão: Encontrado junto à cena.»'},
        {'claim_id': 'courtship', 'origem': 'authored', 'quem_falou': 'rubiao', 'tipo': 'report',
         'conteudo': 'Rubião tenta aproximar-se de Florença, embora ela não corresponda e se incomode com a insistência.'},
    ]}, 'seus_depoimentos_registrados': [
        {'evidence_id': 'cloth', 'nome': 'Lenço de algodão',
         'fala': 'Já vi Dr. Bacamarte com um objeto igual.'},
    ]}


@pytest.mark.parametrize('npc,question,answer', [
    ('capitu', 'olá capitu', 'Boa noite, Floriano. O que o traz aqui?'),
    ('capitu', 'sabe se alguem teria motivos pra desgostar de bras cubas?',
     'Não sei quem guardava rancor de Brás Cubas, Floriano.'),
    ('rubiao', 'olá sr', 'Boa noite, meu senhor.'),
    ('rubiao', 'certo , voce acredita em lobisomens Rubião?',
     'Eu não sei, Floriano. Depois dessas mortes, custa descartar qualquer coisa.'),
    ('rubiao', 'fale comigo homem', 'Estou tentando, Floriano. O que deseja saber de mim?'),
])
async def test_conversation_does_not_become_unrelated_clue(harness,storage,game,llm,npc,question,answer):
    if npc not in {character.character_id for character in game.characters}:
        game=game.model_copy(update={'characters':(*game.characters,GameCharacter(character_id=npc,role='civil'))})
    await storage.games.create(game)
    async def context(*args):
        return observations()
    async def complete(prompt):
        llm.calls.append(prompt)
        return LLMResponse(content=json.dumps({"fala":answer}),model='fake')
    harness._context_provider=context
    llm.complete=complete
    reply=await harness.respond(game.id,npc,uuid4(),'player',question)
    assert reply.message.content==answer


async def test_bras_cubas_question_cannot_use_unrelated_family_facts(catalog):
    profile=await catalog.get('capitu')
    assert dialogue_supports(profile,observations(),'Quem teria motivos para desgostar de Brás Cubas?')==()
    assert dialogue_supports(profile,observations(),'olá capitu')==()


async def test_player_item_presentation_is_not_a_shareable_discovery(catalog):
    supports=dialogue_supports(await catalog.get('rubiao'),observations(),'O que sabe?')
    assert all('Mostro-lhe' not in item['statement'] for item in supports)
    assert any('Bacamarte' in item['statement'] for item in supports)
    assert dialogue_supports(await catalog.get('rubiao'),observations(),'Você acredita em lobisomens, Rubião?')==()


def test_legacy_template_loses_only_automatic_frame_in_prompt():
    text='Posso lhe ajudar com isso: Eu sou casada com Bentinho. Ouça também Bentinho sobre essas discussões.'
    assert historical_dialogue_content(text)=='Eu sou casada com Bentinho.'
    assert historical_dialogue_content('Ouça, Floriano: não sei.')=='Ouça, Floriano: não sei.'


def test_courtesy_validation_cannot_allow_facts_or_confessions():
    assert is_courtesy_reply('fale comigo homem','Homem, o que deseja saber? Diga direto.')
    assert is_courtesy_reply('olá capitu','Olá, Floriano. O que o traz por aqui?')
    assert not is_courtesy_reply('olá capitu','Olá, Floriano. Sou o lobisomem.')
    assert not is_courtesy_reply('olá capitu','Olá, Floriano. Quero me separar de Bentinho.')
    assert not is_courtesy_reply('olá sr','Bom dia, matei Brás Cubas.')


@pytest.mark.parametrize('reply,issue',[
    ('Bom dia, detetive. Pode me chamar de Rubião.', 'wrong_address'),
    ('Olá, meu caro! Que prazer vê-lo por aqui!', 'narrator_style'),
])
async def test_master_false_style_flags_do_not_replace_normal_speech(catalog,reply,issue):
    llm=SimpleNamespace(complete=AsyncMock(return_value=LLMResponse(content=json.dumps({
        'issues':[issue], 'kind':'conversation', 'quote':reply,
        'wrong_address':issue=='wrong_address',
    }),model='fake')))
    turns=SimpleNamespace(require_day_locked=AsyncMock(return_value=SimpleNamespace(day=1)))
    master=SessionMasterService(turns,None,None,llm)
    incoming=ConversationMessage(id=uuid4(),sender_id='player',content='olá sr',created_at=datetime.now(UTC))
    outgoing=ConversationMessage(id=uuid4(),sender_id='rubiao',content=reply,created_at=datetime.now(UTC))
    assessment=await master.assess(uuid4(),'rubiao',uuid4(),incoming,outgoing,
        observations=observations(),profile=await catalog.get('rubiao'))
    assert assessment.issues==() and assessment.corrected_reply is None
