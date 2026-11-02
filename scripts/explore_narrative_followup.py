"""Continua os mesmos encontros de live.jsonl sem abrir novos cenários.

PYTHONPATH=src:scripts .venv/bin/python scripts/explore_narrative_followup.py --stage 2
PYTHONPATH=src:scripts .venv/bin/python scripts/explore_narrative_followup.py --stage 3
As fases preservam IDs/histórico e registram seus próprios tokens incrementais.
"""
import argparse,asyncio,json,sys
from pathlib import Path
from uuid import UUID,NAMESPACE_URL,uuid5
sys.path.insert(0,str(Path(__file__).resolve().parent))
from explore_narrative_balance import NarrativeSimulation,OUT,IDS
import fakeredis
from memorias_licantropicas.settings import Settings
from memorias_licantropicas.contracts.model import GameState,GameCharacter,Conversation,ConversationMessage
from memorias_licantropicas.infrastructure.llm.bedrock_mantle import BedrockMantleClient
from memorias_licantropicas.infrastructure.llm.aws_credentials import ProfileTokenProvider
from memorias_licantropicas.infrastructure.usage import RedisUsageRepository,UsagePricing,MeteredLLMClient
from memorias_licantropicas.modules.knowledge.service import KnowledgeService
from memorias_licantropicas.modules.session_master.service import SessionMasterService
from memorias_licantropicas.modules.agents.service import HarnessService

async def main(stage=2):
 settings=Settings();first=[json.loads(s) for s in (OUT/'live.jsonl').read_text().splitlines()]
 followups=[json.loads(s) for s in (OUT/'live_followup.jsonl').read_text().splitlines()] if stage==3 else []
 path=OUT/('live_quality.jsonl' if stage==3 else 'live_followup.jsonl');done=len(path.read_text().splitlines()) if path.exists() else 0
 for index,record in enumerate(first):
  if index<done or record['status']!='completed':continue
  redis=fakeredis.FakeAsyncRedis(decode_responses=True)
  sim=NarrativeSimulation(redis,f'narrative-live:{index}',43000+index)
  game_id=UUID(record['usage']['game_id']);sim.game_id=game_id
  profiles=await sim.catalog.list()
  game=GameState(id=game_id,created_at=sim.clock(),content_version=sim.catalog.content_version,
    characters=tuple(GameCharacter(character_id=p.id,role='werewolf' if p.id=='bacamarte' else 'civil') for p in profiles))
  await sim.games.create(game);await sim.investigation.get(game_id);await sim.seed_social()
  npc=record['npc_id'];conversation=Conversation(id=uuid5(NAMESPACE_URL,f'live:{npc}'),game_id=game_id,participant_ids=('player',npc),created_at=sim.clock())
  await sim.memory.create_conversation(conversation)
  await sim.memory.append_messages(game_id,conversation.id,(
    ConversationMessage(id=uuid5(NAMESPACE_URL,f'prior:{npc}:question'),sender_id='player',content=record['question'],created_at=sim.clock()),
    ConversationMessage(id=uuid5(NAMESPACE_URL,f'prior:{npc}:reply'),sender_id=npc,content=record['reply'],created_at=sim.clock(),narrative_authorized=True)))
  if stage==3:
   previous=next(r for r in followups if r['npc_id']==npc)
   if previous['status']=='completed':
    await sim.memory.append_messages(game_id,conversation.id,(
      ConversationMessage(id=uuid5(NAMESPACE_URL,f'followup:{npc}:question'),sender_id='player',content=previous['question'],created_at=sim.clock()),
      ConversationMessage(id=uuid5(NAMESPACE_URL,f'followup:{npc}:reply'),sender_id=npc,content=previous['reply'],created_at=sim.clock(),narrative_authorized=True)))
  usage=RedisUsageRepository(redis,sim.prefix,pricing=UsagePricing(model=settings.bedrock_model,input_usd_per_million=settings.llm_input_usd_per_million,
    output_usd_per_million=settings.llm_output_usd_per_million,source=settings.llm_pricing_source,checked_at=settings.llm_pricing_checked_at))
  def client(limit):
   raw=BedrockMantleClient(base_url=settings.mantle_base_url,api_key=settings.bedrock_api_key.get_secret_value() if settings.bedrock_api_key else None,
    model=settings.bedrock_model,timeout_seconds=20,max_tokens=limit,token_provider=ProfileTokenProvider(settings.aws_profile,settings.aws_region) if settings.aws_profile else None)
   return MeteredLLMClient(raw,usage,configured_model=settings.bedrock_model)
  llm,judge=client(240),client(640)
  knowledge=KnowledgeService(sim.social_repository,sim.catalog,judge,clock=sim.clock)
  master=SessionMasterService(sim.turns,sim.games,sim.memory,judge,redis,sim.prefix)
  harness=HarnessService(sim.catalog,sim.games,sim.memory,llm,day_policy=sim.turns,context_provider=sim.investigation.npc_context_locked,knowledge_provider=knowledge.context,session_master=master)
  question=('Entendi. O que você sabe de verdade, e em que pode me ajudar agora?' if stage==3 else 'E o que você acha disso, pessoalmente? Por onde eu começo?')
  result={'npc_id':npc,'game_id':str(game_id),'same_scenario_followup':True,'question':question}
  try:
   async with sim.gate.hold(game_id):reply=await harness.respond(game_id,npc,conversation.id,'player',question)
   result.update(status='completed',reply=reply.message.content)
  except Exception as exc:result.update(status='failed',error_code=getattr(exc,'code',type(exc).__name__))
  state=await sim.turns.sync(game_id)
  result['assessments']=[event['assessment'] for event in state.dialogue_events]
  result['usage']=(await usage.summary(game_id)).model_dump(mode='json')
  with path.open('a') as stream:stream.write(json.dumps(result,ensure_ascii=False)+'\n')
  print(npc,result['status'],flush=True)
  await llm.aclose();await judge.aclose();await redis.aclose()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--stage',type=int,choices=[2,3],default=2)
 asyncio.run(main(parser.parse_args().stage))
