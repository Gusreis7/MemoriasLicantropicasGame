"""100 partidas passivas isoladas, com motor/Redis simulados e sem chamadas LLM/AWS."""
import asyncio,json,sys
from pathlib import Path
from collections import Counter
import fakeredis

sys.path.insert(0,str(Path(__file__).resolve().parent))
from simulate_gameplay import Simulation
from memorias_licantropicas.contracts.investigation import NightStory,MurderPlot

async def main():
 rows=[]
 for index in range(100):
  redis=fakeredis.FakeAsyncRedis(decode_responses=True)
  try:
   sim=Simulation(redis,f'v4:validation:{index}',44000+index)
   profiles=await sim.catalog.list();wolf=profiles[index%len(profiles)].id
   await sim.create(wolf)
   state=await sim.turns.sync(sim.game_id)
   civils=[p.id for p in profiles if p.id!=wolf]
   planner=civils[index%len(civils)];target=next(p for p in civils[(index//len(civils))%len(civils):]+civils if p!=planner)
   story=NightStory(seed=f'synthetic-validation-{index}',plot=MurderPlot(planner_id=planner,target_id=target))
   state=state.model_copy(update={'night_story':story})
   key=f'{sim.prefix}:game:{{{sim.game_id}}}:investigation'
   await redis.set(key,state.model_dump_json())
   nights=[];previous_quiet=False
   for _ in range(2*len(civils)+2):
    public=await sim.next_morning();updated=await sim.turns.sync(sim.game_id)
    fresh=updated.crimes[len(state.crimes):]
    wolf_kills=sum(c.cause=='werewolf' for c in fresh);civil_kills=sum(c.cause=='civil' for c in fresh)
    assert not (previous_quiet and not wolf_kills),'Two consecutive nights without a wolf kill'
    assert len(fresh)<=2 and len({c.victim_id for c in updated.crimes})==len(updated.crimes)
    for c in fresh:assert c.killer_id==(wolf if c.cause=='werewolf' else planner)
    nights.append({'night':state.day,'werewolf_deaths':wolf_kills,'civil_deaths':civil_kills})
    previous_quiet=not wolf_kills
    state=updated
    if public.status!='active':break
   assert public.status=='lost' and not any(m.role=='civil' and m.alive for m in (await sim.games.get(sim.game_id)).characters)
   rows.append({'case_id':index,'werewolf':wolf,'planner':planner,'target':target,'nights':nights,
                'ending_day':state.day,'result':state.status,'plot_status':state.night_story.plot.status})
  finally:await redis.aclose()
 out=Path('docs/validacao_relacoes_noites_v4');out.mkdir(exist_ok=True)
 (out/'partidas.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 counts=Counter(str(n['werewolf_deaths']+n['civil_deaths']) for r in rows for n in r['nights'])
 summary={'games':len(rows),'llm_calls':0,'estimated_llm_cost_usd':'0','night_death_counts':dict(counts),
          'civil_homicides':sum(n['civil_deaths'] for r in rows for n in r['nights']),
          'plot_outcomes':dict(Counter(r['plot_status'] for r in rows)),
          'ending_day_min':min(r['ending_day'] for r in rows),'ending_day_max':max(r['ending_day'] for r in rows),
          'invariant_failures':0,'method':'Passive programmed player; no dialogue quality or human balance measurement.'}
 (out/'resumo.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))

asyncio.run(main())
