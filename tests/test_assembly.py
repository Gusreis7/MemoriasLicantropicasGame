from datetime import timedelta
from uuid import uuid4
import pytest
from test_interrogations import inquiry, dossier
from src.contracts.errors import ConflictError
from src.infrastructure.social_repository import RedisSocialRepository
from src.modules.investigation.assembly import convene
from src.modules.world.motion import project_npc
from src.modules.world.model import WorldNPC

pytestmark = pytest.mark.anyio

async def test_correct_majority_wins_atomically_and_only_once(inquiry):
    state, game, evidence, testimony = await dossier(inquiry)
    await inquiry.storage.client.set(inquiry.key + ':investigation', state.model_dump_json())
    result = await inquiry.service.assemble(game.id, 'capitu', evidence, testimony)
    assert result.status == 'won' and result.ending.method == 'assembly'
    assert result.assembly['required_votes'] == 5
    assert (await inquiry.storage.games.get(game.id)).status == 'won'
    assert 'capitu' not in {n.npc_id for n in (await inquiry.world.get(game.id)).npcs}
    with pytest.raises(ConflictError):
        await inquiry.service.assemble(game.id, 'bentinho')

async def test_insufficient_votes_consume_single_assembly(inquiry):
    result = await inquiry.service.assemble(inquiry.game.id, 'capitu')
    assert result.assembly['outcome'] == 'no_majority' and result.status == 'active'
    with pytest.raises(ConflictError):
        await inquiry.service.assemble(inquiry.game.id, 'bentinho')

async def test_wrong_expulsion_increases_real_social_resentment_and_preserves_life(inquiry):
    state, game, evidence, testimony = await dossier(inquiry)
    statements = tuple(t.model_copy(update={'recognition':'recognizes','claimed_owner_id':'bentinho'}) for t in state.testimonies)
    state = state.model_copy(update={'testimonies': statements})
    await inquiry.storage.client.set(inquiry.key + ':investigation', state.model_dump_json())
    result = await inquiry.service.assemble(game.id, 'bentinho', evidence, testimony)
    assert result.status == 'active' and result.assembly['outcome'] == 'innocent'
    assert result.expelled_npc_ids == ('bentinho',)
    assert next(m for m in (await inquiry.storage.games.get(game.id)).characters if m.character_id == 'bentinho').alive
    social = await RedisSocialRepository(inquiry.storage.client, inquiry.storage.prefix).get(game.id)
    assert social.relationships and all(r.resentment >= 5 for r in social.relationships if r.actor_id!=r.target_id and r.actor_id in {m.character_id for m in game.characters} and r.target_id in {*[m.character_id for m in game.characters],"player"})
    assert 'bentinho' not in {n.npc_id for n in (await inquiry.world.get(game.id)).npcs}

async def test_assembly_blocked_at_night(inquiry):
    await inquiry.turns.sync(inquiry.game.id)
    inquiry.clock[0] += timedelta(seconds=300)
    with pytest.raises(ConflictError):
        await inquiry.service.assemble(inquiry.game.id, 'capitu')

async def test_route_is_visible_in_each_location_with_monotonic_positions(inquiry):
    now = inquiry.clock[0]
    npc = WorldNPC(npc_id='capitu', location_id='praca_verde', x=400, activity='travelling',
        travel_started_at=now, travel_arrives_at=now+timedelta(seconds=20),
        travel_origin_x=400, travel_target_x=460, travel_route=('praca_verde','casa_verde'))
    assert project_npc(npc, now) == ('praca_verde',400)
    assert project_npc(npc,now+timedelta(seconds=5)) == ('praca_verde',664)
    assert project_npc(npc,now+timedelta(seconds=15)) == ('casa_verde',246)
    assert project_npc(npc,now+timedelta(seconds=20)) == ('casa_verde',460)

async def test_concurrent_assembly_cannot_resolve_twice(inquiry):
    import asyncio
    results = await asyncio.gather(inquiry.service.assemble(inquiry.game.id,'capitu'),
        inquiry.service.assemble(inquiry.game.id,'bentinho'), return_exceptions=True)
    assert sum(not isinstance(r,Exception) for r in results) == 1
    state = await inquiry.turns.sync(inquiry.game.id)
    assert state.assembly is not None

async def test_assembly_http_never_accepts_client_votes(api_client):
    game = (await api_client.post('/api/v1/games',json={})).json()
    path = f"/api/v1/games/{game['id']}/assembly"
    assert (await api_client.post(path,json={'suspect_id':'capitu','votes':[]})).status_code == 422
    response = await api_client.post(path,json={'suspect_id':'capitu','evidence_ids':[],'testimony_ids':[]})
    assert response.status_code == 200 and response.json()['assembly']['outcome'] == 'no_majority'
    assert (await api_client.post(path,json={'suspect_id':'capitu'})).status_code == 409

from test_world import world_context

async def test_world_projects_walking_npc_and_blocks_approach(world_context):
    ctx = world_context
    now = ctx.clock[0]
    world = ctx.initial.model_copy(update={'revision':1,'npcs':tuple(n.model_copy(update={
        'activity':'travelling','travel_started_at':now,'travel_arrives_at':now+timedelta(seconds=20),
        'travel_origin_x':n.x,'travel_target_x':460,'travel_route':('praca_verde','casa_verde')})
        if n.npc_id == 'rubiao' else n for n in ctx.initial.npcs)})
    await ctx.repository.save(world,0)
    ctx.clock[0] += timedelta(seconds=2)
    snapshot = await ctx.service.get(ctx.game.id)
    actor = next(n for n in snapshot.visible_npcs if n.npc_id == 'rubiao')
    assert actor.activity == 'travelling' and actor.x > 440 and not actor.can_approach
    assert any(n['npc_id'] == 'rubiao' for n in snapshot.npc_presences)
