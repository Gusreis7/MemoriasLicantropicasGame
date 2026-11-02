from datetime import timedelta
from uuid import uuid4
import pytest
from test_interrogations import inquiry, dossier
from memorias_licantropicas.contracts.errors import ConflictError
from memorias_licantropicas.infrastructure.social_repository import RedisSocialRepository
from memorias_licantropicas.contracts.social import SocialState
from memorias_licantropicas.modules.knowledge.rules import initial_relationships

pytestmark=pytest.mark.anyio

async def test_short_assembly_pauses_rejects_actions_and_restores_remaining_time(inquiry):
    original=await inquiry.service.get(inquiry.game.id)
    opened=await inquiry.service.open_assembly(inquiry.game.id,'capitu',speech='Quero ouvir a cidade antes de decidir.')
    assert opened.assembly is None and opened.assembly_session['phase']=='debate'
    assert 'relationships' not in opened.assembly_session
    assert 'argument_strength' not in opened.assembly_session
    with pytest.raises(ConflictError):
        await inquiry.service.interrogate(inquiry.game.id,'capitu',0)
    inquiry.clock[0]+=timedelta(seconds=12)
    resolved=await inquiry.service.resolve_assembly(inquiry.game.id,'Ainda faltam elementos. Peço cautela.')
    assert resolved.assembly is not None
    assert resolved.phase_ends_at==original.phase_ends_at+timedelta(seconds=12)
    again=await inquiry.service.resolve_assembly(inquiry.game.id,'Texto ignorado em retry.')
    assert again.assembly==resolved.assembly

async def test_timeout_resolves_without_extending_a_day_indefinitely(inquiry):
    original=await inquiry.service.get(inquiry.game.id)
    await inquiry.service.open_assembly(inquiry.game.id,'capitu',speech='Vamos ouvir as versões.')
    inquiry.clock[0]+=timedelta(seconds=61)
    resolved=await inquiry.service.get(inquiry.game.id)
    assert resolved.assembly_session['phase']=='resolved' and resolved.assembly is not None
    assert resolved.phase_ends_at==original.phase_ends_at+timedelta(seconds=60)
    with pytest.raises(ConflictError):
        await inquiry.service.open_assembly(inquiry.game.id,'escobar')

async def test_hostile_city_can_expel_player_atomically(inquiry):
    repo=RedisSocialRepository(inquiry.storage.client,inquiry.storage.prefix)
    relations=initial_relationships(tuple(m.character_id for m in inquiry.game.characters))
    relations=tuple(r.model_copy(update={'trust':-100,'affinity':-80,'resentment':100,'suspicion':100}) if r.target_id=='player' else r for r in relations)
    state=SocialState(game_id=inquiry.game.id,revision=1,relationships=relations)
    assert await repo.save(state,0)
    inquiry.service._social_repository=repo
    await inquiry.service.open_assembly(inquiry.game.id,'capitu',speech='Todos devem obedecer às minhas acusações.')
    result=await inquiry.service.resolve_assembly(inquiry.game.id)
    assert result.status=='lost' and result.ending.method=='player_expelled'
    assert result.assembly['outcome']=='player_expelled'
    assert (await inquiry.storage.games.get(inquiry.game.id)).status=='lost'
    assert 'Floriano' in result.journal[-1].headline
    assert 'player' not in result.expelled_npc_ids
    assert sum(v['target_id']=='player' for v in result.assembly['votes'])>=result.assembly['required_votes']

async def test_short_dossier_can_win_and_public_debate_has_no_private_roles(inquiry):
    state,game,evidence,testimony=await dossier(inquiry)
    await inquiry.storage.client.set(inquiry.key+':investigation',state.model_dump_json())
    opened=await inquiry.service.open_assembly(game.id,'capitu',evidence,testimony,'Os objetos e as testemunhas apontam contradições; ouçam os relatos.')
    assert len(opened.assembly_session['messages'])==8
    assert 'roles' not in str(opened.assembly_session)
    result=await inquiry.service.resolve_assembly(game.id,'Peço que avaliem os registros apresentados.')
    assert result.status=='won' and result.ending.method=='assembly'
    assert (await inquiry.storage.games.get(game.id)).status=='won'

async def test_short_assembly_references_and_limits_are_validated_before_consuming(inquiry):
    with pytest.raises(Exception):
        await inquiry.service.open_assembly(inquiry.game.id,'capitu',(uuid4(),),(),speech='Uma alegação.')
    state=await inquiry.turns.sync(inquiry.game.id)
    assert state.assembly_session is None
    with pytest.raises(ConflictError):
        await inquiry.service.open_assembly(inquiry.game.id,'capitu',speech='x'*801)
    assert (await inquiry.turns.sync(inquiry.game.id)).assembly_session is None

async def test_new_http_rejects_forged_votes_and_accepts_short_payload(api_client):
    game=(await api_client.post('/api/v1/games',json={})).json()
    root=f"/api/v1/games/{game['id']}/assembly"
    assert (await api_client.post(root+'/open',json={'suspect_id':'capitu','speech':'x'*801})).status_code==422
    assert (await api_client.post(root+'/open',json={'suspect_id':'capitu','votes':[]})).status_code==422
    opened=await api_client.post(root+'/open',json={'suspect_id':'capitu','speech':'Vamos ouvir os moradores.'})
    assert opened.status_code==200
    resolved=await api_client.post(root+'/resolve',json={'reply':'Peço cautela.'})
    assert resolved.status_code==200 and resolved.json()['assembly'] is not None
