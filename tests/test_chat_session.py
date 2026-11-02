from datetime import timedelta
from uuid import UUID
import pytest
from test_conversations import open_conversation
from test_social_service import social_case, seed_claim
from memorias_licantropicas.modules.world.service import WorldService
from memorias_licantropicas.modules.world.model import WorldState

pytestmark = pytest.mark.anyio

async def test_open_chat_keeps_npc_out_of_social_schedule_and_release_restores_availability(social_case, catalog):
    c=social_case
    await seed_claim(c)
    w=await c.world.get(c.game.id)
    target=next(n for n in w.npcs if n.npc_id=='capitu')
    await c.world.save(w.model_copy(update={'revision':w.revision+1,'player':w.player.model_copy(update={'location_id':target.location_id,'x':target.x})}),w.revision)
    service=WorldService(c.games,catalog,c.world,c.gate,clock=lambda:c.now[0],day_policy=c.turns,on_approach=c.service.interrupt)
    async with c.gate.hold(c.game.id):await service.assert_can_talk(c.game.id,'capitu')
    assert next(n for n in (await c.world.get(c.game.id)).npcs if n.npc_id=='capitu').player_engaged_until == c.now[0]+timedelta(seconds=90)
    c.now[0]+=timedelta(seconds=30)
    async with c.gate.hold(c.game.id):await service.assert_can_talk(c.game.id,'capitu')
    assert next(n for n in (await c.world.get(c.game.id)).npcs if n.npc_id=='capitu').player_engaged_until == c.now[0]+timedelta(seconds=90)
    c.now[0]+=timedelta(seconds=30)
    await c.service.tick(c.game.id)
    assert all('capitu' not in e.participant_ids for e in (await c.repository.get(c.game.id)).encounters)
    async with c.gate.hold(c.game.id):await service.release_dialogue(c.game.id,'capitu')
    assert next(n for n in (await c.world.get(c.game.id)).npcs if n.npc_id=='capitu').player_engaged_until is None

async def test_away_npc_returns_safe_reason_without_llm_and_history_remains_readable(api_client,storage,llm):
    game,conversation=await open_conversation(api_client,storage)
    key=f"{storage.prefix}:game:{{{game['id']}}}:world"
    w=WorldState.model_validate_json(await storage.client.get(key))
    w=w.model_copy(update={'revision':w.revision+1,'npcs':tuple(n.model_copy(update={'location_id':'casa_verde'}) if n.npc_id=='capitu' else n for n in w.npcs)})
    await storage.client.set(key,w.model_dump_json())
    base=f"/api/v1/games/{game['id']}/conversations/{conversation['id']}"
    response=await api_client.post(base+'/messages',json={'content':'Olá'})
    assert response.status_code==403 and response.json()['code']=='npc_away'
    assert 'saiu deste local' in response.json()['detail'] and not llm.calls
    assert (await api_client.get(base+'/messages')).status_code==200
    assert (await api_client.post(base+'/close',json={})).status_code==204

async def test_dead_npc_history_is_preserved_but_cannot_receive_messages(api_client,storage):
    game,conversation=await open_conversation(api_client,storage)
    base=f"/api/v1/games/{game['id']}/conversations/{conversation['id']}"
    assert (await api_client.post(base+'/messages',json={'content':'Bom dia'})).status_code==200
    state=await storage.games.get(UUID(game['id']))
    state=state.model_copy(update={'characters':tuple(n.model_copy(update={'alive':False}) if n.character_id=='capitu' else n for n in state.characters)})
    await storage.client.set(f"{storage.prefix}:game:{{{game['id']}}}:state",state.model_dump_json())
    history=await api_client.get(base+'/messages')
    assert history.status_code==200 and len(history.json()['messages'])==2
    assert (await api_client.post(base+'/messages',json={'content':'Olá'})).status_code==403

async def test_abandoned_chat_lease_expires_and_does_not_stop_future_meetings(social_case,catalog):
    c=social_case
    await seed_claim(c)
    w=await c.world.get(c.game.id)
    target=next(n for n in w.npcs if n.npc_id=='capitu')
    await c.world.save(w.model_copy(update={'revision':w.revision+1,'player':w.player.model_copy(update={'location_id':target.location_id,'x':target.x})}),w.revision)
    service=WorldService(c.games,catalog,c.world,c.gate,clock=lambda:c.now[0],day_policy=c.turns)
    async with c.gate.hold(c.game.id):await service.assert_can_talk(c.game.id,'capitu')
    c.now[0]=c.game.created_at+timedelta(seconds=120)
    await c.service.tick(c.game.id)
    assert 'capitu' in (await c.repository.get(c.game.id)).encounters[-1].participant_ids
