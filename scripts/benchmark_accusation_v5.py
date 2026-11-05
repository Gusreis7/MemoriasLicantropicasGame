"""100 partidas por variante; motor real, Redis isolado, políticas públicas, sem LLM."""
import argparse,asyncio,json,sys
from pathlib import Path
from uuid import UUID,NAMESPACE_URL,uuid5
from collections import Counter
import fakeredis

parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['before','after'],required=True)
parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();root=args.source_root.resolve()
sys.path[:0]=[str(root),str(root/'scripts')]
from simulate_gameplay import Simulation
from src.contracts.model import GameState,GameCharacter
from src.contracts.investigation import NightStory,MurderPlot
from src.contracts.errors import ConflictError,AccessDeniedError
from src.modules.investigation.catalog import INVENTORIES

POLICIES=('examining','witness_first','common_only','one_source','rework')
class Run(Simulation):
 async def create(self,wolf):
  profiles=await self.catalog.list()
  game=GameState(id=uuid5(NAMESPACE_URL,f'accusation-v5:{self.seed}'),created_at=self.clock(),content_version=self.catalog.content_version,
       characters=tuple(GameCharacter(character_id=p.id,role='werewolf' if p.id==wolf else 'civil') for p in profiles))
  assert await self.games.create(game);self.game_id=game.id
  state=await self.turns.sync(game.id)
  civils=[p.id for p in profiles if p.id!=wolf];actor=civils[self.seed%len(civils)];target=next(p for p in civils if p!=actor)
  story=NightStory(seed=f'paired-accusation-v5:{self.seed}',plot=MurderPlot(planner_id=actor,target_id=target))
  state=state.model_copy(update={'night_story':story})
  await self.redis.set(f'{self.prefix}:game:{{{game.id}}}:investigation',state.model_dump_json())
  return await self.investigation.get(game.id)

 async def play_policy(self,wolf,policy):
  case=await self.create(wolf);attempts=[];rework_done=False
  for _ in range(16):
   if case.status!='active':break
   case=await self.collect(case)
   if policy=='examining':
    for item in case.inventory:
     if not item.examined:case=await self.investigation.inspect(self.game_id,item.id)
   case,living=await self.survey(case)
   if case.status!='active':break
   evidence={e.id:e for e in case.inventory}
   eligible=set(living)-set(case.expelled_npc_ids)
   candidates=[]
   for npc in eligible:
    records=[t for t in case.testimonies if t.recognition=='recognizes' and t.claimed_owner_id==npc]
    kinds={evidence[t.evidence_id].item_id:evidence[t.evidence_id].kind for t in records}
    score=sum(3 for k in kinds.values() if k=='unique')+min(2,sum(1 for k in kinds.values() if k=='singular'))+min(.5,sum(.25 for k in kinds.values() if k=='common'))
    candidates.append((-score,npc,records))
   if candidates:
    _,npc,records=min(candidates,key=lambda c:(c[0],c[1]))
    ev=tuple(e.id for e in case.inventory if policy!='common_only' or e.kind=='common')
    types={evidence[i].item_id for i in ev}
    ts=tuple(t.id for t in case.testimonies if evidence[t.evidence_id].item_id in types)
    if policy=='one_source' and records:
     witness=next((t.witness_id for t in records if t.witness_id!=npc),records[0].witness_id)
     ts=tuple(t.id for t in case.testimonies if t.id in ts and t.witness_id==witness)
    if policy=='rework':
     enough=any(e.kind=='unique' for e in case.inventory)
     if enough and not rework_done:
      case=await self.investigation.accuse(self.game_id,npc,(),());rework_done=True
     if enough:
      for item in case.inventory:
       if not item.examined:case=await self.investigation.inspect(self.game_id,item.id)
    before=case.day
    try:
     case=await self.investigation.accuse(self.game_id,npc,ev,ts)
     record=case.accusations[-1]
     attempts.append({'day':before,'suspect':npc,'accepted':record.accepted,'reason':record.reason})
    except (ConflictError,AccessDeniedError) as exc:
     attempts.append({'day':before,'suspect':npc,'blocked':type(exc).__name__,'reason':str(exc)})
   if case.status=='active':case=await self.next_morning()
  return {'result':case.status,'ending_day':case.day,'attempts':attempts,
          'first_accepted_day':next((a['day'] for a in attempts if a.get('accepted')),None),
          'wrong_detentions':sum(a.get('accepted',False) and a['suspect']!=wolf for a in attempts),
          'crimes':len(case.crimes),'testimonies':len(case.testimonies)}

async def main():
 args.output.mkdir(parents=True,exist_ok=True);path=args.output/f'{args.phase}.jsonl'
 assert not path.exists(),'Keep archived trials immutable; choose a new output directory'
 sem=asyncio.Semaphore(4)
 async def one(index):
  async with sem:
   redis=fakeredis.FakeAsyncRedis(decode_responses=True)
   try:
    seed=55000+index;wolf=tuple(INVENTORIES)[index%len(INVENTORIES)];policy=POLICIES[index%len(POLICIES)]
    sim=Run(redis,f'v5:{args.phase}:{index}',seed)
    result=await sim.play_policy(wolf,policy)
    row={'case_id':index,'seed':seed,'werewolf':wolf,'policy':policy,**result,'llm_calls':0}
    assert row['result'] in ('won','lost'),row
    with path.open('a') as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
   finally:await redis.aclose()
 await asyncio.gather(*(one(i) for i in range(100)))
 rows=[json.loads(l) for l in path.read_text().splitlines()]
 print(json.dumps({p:{'games':sum(r['policy']==p for r in rows),'won':sum(r['policy']==p and r['result']=='won' for r in rows),'wrong_detentions':sum(r['wrong_detentions'] for r in rows if r['policy']==p)} for p in POLICIES},ensure_ascii=False))

asyncio.run(main())
