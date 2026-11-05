"""Teto100 cenários:21 tentativas iniciais+72 jogos seguintes+7 encontros reais.
A divisão efetiva de calibragem/holdout está documentada no relatório; checkpoints preservam falhas.

PYTHONPATH=.:scripts .venv/bin/python scripts/explore_narrative_balance.py --phase calibration
PYTHONPATH=.:scripts .venv/bin/python scripts/explore_narrative_balance.py --phase validation
PYTHONPATH=.:scripts .venv/bin/python scripts/explore_narrative_balance.py --phase live
Persistência fakeredis isolada; nunca consulta/altera o Redis da aplicação.
"""
import argparse,asyncio,json,random
from collections import Counter
from datetime import timedelta
from pathlib import Path
from time import monotonic
from unittest.mock import patch
from uuid import NAMESPACE_URL,uuid5
import fakeredis
from simulate_gameplay import Simulation,rank_suspects
from src.contracts.errors import ConflictError,AccessDeniedError,LLMUnavailableError
from src.contracts.model import LLMResponse
from src.modules.knowledge.seeds import seed_social_state
from src.modules.knowledge.rules import apply_relationship
from src.modules.knowledge.mechanics import closeness
from src.modules.agents.service import HarnessService
from src.modules.session_master.service import SessionMasterService
from src.modules.conversations.service import ConversationService
from src.infrastructure.conversation_gate import RedisConversationGate
from src.modules.characters.catalog import PUBLIC_BIOS

OUT=Path('docs/exploracao_narrativa')
IDS=tuple(PUBLIC_BIOS)
POLICIES=('assembly_informed','detention_informed','hostile_rash','passive','rash','natural_confession')

class ScriptedPersona:
    def __init__(self,games,game_id,npc_id): self.games,self.game_id,self.npc_id=games,game_id,npc_id
    async def complete(self,messages,*,tools=(),tool_choice=None):
        game=await self.games.get(self.game_id)
        member=next(m for m in game.characters if m.character_id==self.npc_id)
        # Test generator knows role exactly as the persona would; detector policy never sees it.
        text='Fui eu quem matou Brás Cubas. Entrego-me ao delegado.' if member.role=='werewolf' else 'Não cometi esses ataques, Floriano. Quero esclarecer minha versão.'
        return LLMResponse(model='scripted-persona', tool_calls=({'name':tools[0]['function']['name'],'args':{'fala':text},'id':'scripted-call','type':'tool_call'},))

class NarrativeSimulation(Simulation):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.investigation._memory=self.memory
        self.investigation._social_repository=self.social_repository
    async def seed_social(self):
        social=await self.social_repository.get(self.game_id)
        updated=seed_social_state(social,IDS,self.clock()).model_copy(update={'revision':social.revision+1})
        assert await self.social_repository.save(updated,social.revision)
    async def survey(self,case):
        # Same movement/presentation services as production; no formal alibi endpoint.
        living=set()
        for location in __import__('src.modules.world.catalog',fromlist=['LOCATIONS']).LOCATIONS:
            snapshot=await self.walk_to(location.id,160)
            for visible in snapshot.visible_npcs:
                living.add(visible.npc_id)
                await self.walk_to(location.id,visible.x)
                for evidence in case.inventory:
                    if any(t.witness_id==visible.npc_id and next((e.item_id for e in case.inventory if e.id==t.evidence_id),None)==evidence.item_id for t in case.testimonies): continue
                    case=await self.investigation.present(self.game_id,evidence.id,visible.npc_id)
                    self.actions['present']+=1; self.clock.advance(1)
        return case,living
    async def hostility(self,steps=12):
        social=await self.social_repository.get(self.game_id)
        for index in range(steps):
            cause=uuid5(NAMESPACE_URL,f'{self.seed}:hostile:{index}')
            for actor in IDS:
                social=apply_relationship(social,actor,'player',cause,trust=-5,affinity=-3,resentment=5,suspicion=5)
        previous=await self.social_repository.get(self.game_id)
        social=social.model_copy(update={'revision':previous.revision+1})
        assert await self.social_repository.save(social,previous.revision)
        self.actions['scripted_hostile_events']=steps
    async def natural_confess(self,suspect):
        from src.modules.world.catalog import LOCATIONS
        for location in LOCATIONS:
            snap=await self.walk_to(location.id,160)
            npc=next((n for n in snap.visible_npcs if n.npc_id==suspect),None)
            if not npc: continue
            await self.walk_to(location.id,npc.x)
            llm=ScriptedPersona(self.games,self.game_id,suspect)
            master=SessionMasterService(self.turns,self.games,self.memory,redis=self.redis,prefix=self.prefix)
            harness=HarnessService(self.catalog,self.games,self.memory,llm,day_policy=self.turns,
                context_provider=self.investigation.npc_context_locked,session_master=master)
            service=ConversationService(self.catalog,self.games,self.memory,harness,
                RedisConversationGate(self.redis,self.prefix),self.world,self.gate)
            conversation=await service.create(self.game_id,suspect)
            await service.send(self.game_id,conversation.id,'As versões e os objetos se contradizem. O que aconteceu com Brás Cubas?')
            self.actions['scripted_natural_exchange']+=1
            break
        return await self.investigation.get(self.game_id)
    async def run(self,wolf,policy):
        start=monotonic(); case=await self.create(wolf); await self.seed_social()
        if policy=='hostile_rash': await self.hostility()
        errors=[]
        for _ in range(9):
            if case.status!='active': break
            try:
                if policy=='passive':
                    case=await self.next_morning(); continue
                if policy=='hostile_rash':
                    suspect=self.rng.choice(sorted(m.character_id for m in (await self.games.get(self.game_id)).characters if m.alive))
                    case=await self.investigation.open_assembly(self.game_id,suspect,speech='Obedeçam. Não devo explicações a ninguém.')
                    self.clock.advance(6); case=await self.investigation.resolve_assembly(self.game_id,'Façam o que eu mandei.')
                elif policy=='rash' and not case.assembly:
                    case=await self.collect(case)
                    names=sorted(m.character_id for m in (await self.games.get(self.game_id)).characters if m.alive)
                    suspect=self.rng.choice(names)
                    case=await self.investigation.open_assembly(self.game_id,suspect,
                        tuple(e.id for e in case.inventory),(),speech='Desconfio desta pessoa; quero ouvir as opiniões dos moradores.')
                    self.clock.advance(9);case=await self.investigation.resolve_assembly(self.game_id)
                else:
                    case=await self.collect(case);case,living=await self.survey(case)
                    ranked=rank_suspects(case,living-set(case.expelled_npc_ids))
                    top=ranked[0] if ranked else None
                    tie=len(ranked)>1 and ranked[0]['score']==ranked[1]['score']
                    self.trace.append({'day':case.day,'public_ranking':ranked})
                    if top and top['types']>=2 and top['score']>=4 and not tie:
                        suspect=top['npc_id']; evidence=tuple(e.id for e in case.inventory); testimony=tuple(t.id for t in case.testimonies)
                        if policy=='natural_confession':
                            case=await self.natural_confess(suspect)
                        elif policy=='detention_informed' or case.assembly:
                            case=await self.investigation.accuse(self.game_id,suspect,evidence,testimony)
                        else:
                            case=await self.investigation.open_assembly(self.game_id,suspect,evidence,testimony,
                                'Os objetos e os relatos apontam contradições. Comparem as fontes e ouçam também a defesa.')
                            self.clock.advance(15)
                            case=await self.investigation.resolve_assembly(self.game_id,'Peço que votem pelas versões e pelas pistas apresentadas, porque elas se confirmam entre fontes diferentes.')
                if case.status=='active': case=await self.next_morning()
            except (ConflictError,AccessDeniedError) as exc:
                errors.append({'day':case.day,'type':type(exc).__name__,'detail':str(exc)})
                case=await self.next_morning()
        private=await self.games.get(self.game_id)
        actual=next(m.character_id for m in private.characters if m.role=='werewolf')
        social=await self.social_repository.get(self.game_id)
        return {'seed':self.seed,'policy':policy,'wolf':actual,'result':case.status,'day':case.day,
            'method':case.ending.method if case.ending else None,'assembly':case.assembly,
            'actions':dict(self.actions),'public_trace':self.trace,'errors':errors,
            'factual_false_confession_wins':sum(e.get('accepted_confession',False) and e['npc_id']!=actual for e in (await self.turns.sync(self.game_id)).dialogue_events),
            'seeded_knowledge':len(social.knowledge),'gossip_roots':len({e.root_id for e in social.knowledge}),
            'runtime_seconds':round(monotonic()-start,4),'provider_calls':0,'measured_input_tokens':0,'measured_output_tokens':0}

async def run_games(phase, limit=None):
    OUT.mkdir(parents=True,exist_ok=True)
    count=21 if phase=='calibration' else 72
    if limit is not None: count=min(count,limit)
    offset=0 if phase=='calibration' else 21
    path=OUT/f'{phase}.jsonl'
    existing=[json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
    # Checkpoint: rerunning never silently creates additional completed games.
    for index in range(len(existing),count):
        seed=42000+offset+index
        wolf=IDS[(offset+index)%len(IDS)]
        policy=(('assembly_informed','detention_informed','hostile_rash')[index%3] if phase=='calibration' else POLICIES[index%len(POLICIES)])
        redis=fakeredis.FakeAsyncRedis(decode_responses=True)
        sim=NarrativeSimulation(redis,f'narrative-explore:{seed}',seed)
        try:
            result=await sim.run(wolf,policy)
        except Exception as exc:
            result={'seed':seed,'policy':policy,'wolf':wolf,'result':'error','error':type(exc).__name__,'detail':str(exc)}
        finally: await redis.aclose()
        with path.open('a') as stream: stream.write(json.dumps(result,ensure_ascii=False,default=str)+'\n')
        print(phase,index+1,policy,result['result'],result.get('method'),flush=True)
        if result['result']=='error': raise SystemExit('Unexpected error: checkpoint saved; fix before continuing.')

async def run_live():
    from src.settings import Settings
    from src.infrastructure.llm.bedrock_mantle import BedrockMantleClient
    from src.infrastructure.llm.aws_credentials import ProfileTokenProvider
    from src.infrastructure.usage import MeteredLLMClient,RedisUsageRepository,UsagePricing
    settings=Settings();OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'live.jsonl'
    done=len(path.read_text().splitlines()) if path.exists() else 0
    for index,npc in enumerate(IDS):
        if index<done: continue
        redis=fakeredis.FakeAsyncRedis(decode_responses=True)
        sim=NarrativeSimulation(redis,f'narrative-live:{index}',43000+index)
        await sim.create('bacamarte');await sim.seed_social()
        pricing=UsagePricing(model=settings.bedrock_model,input_usd_per_million=settings.llm_input_usd_per_million,
            output_usd_per_million=settings.llm_output_usd_per_million,source=settings.llm_pricing_source,checked_at=settings.llm_pricing_checked_at)
        usage=RedisUsageRepository(redis,sim.prefix,pricing=pricing)
        raw=BedrockMantleClient(base_url=settings.mantle_base_url,
            api_key=settings.bedrock_api_key.get_secret_value() if settings.bedrock_api_key else None,
            model=settings.bedrock_model,timeout_seconds=20,max_tokens=512,
            token_provider=ProfileTokenProvider(settings.aws_profile,settings.aws_region) if settings.aws_profile else None)
        client=MeteredLLMClient(raw,usage,configured_model=settings.bedrock_model)
        from src.modules.knowledge.service import KnowledgeService
        knowledge=KnowledgeService(sim.social_repository,sim.catalog,client,clock=sim.clock)
        master=SessionMasterService(sim.turns,sim.games,sim.memory,client,redis,sim.prefix)
        harness=HarnessService(sim.catalog,sim.games,sim.memory,client,day_policy=sim.turns,
            context_provider=sim.investigation.npc_context_locked,knowledge_provider=knowledge.context,session_master=master)
        from src.contracts.model import Conversation
        conversation=Conversation(id=uuid5(NAMESPACE_URL,f'live:{npc}'),game_id=sim.game_id,
            participant_ids=('player',npc),created_at=sim.clock())
        await sim.memory.create_conversation(conversation)
        question={'bentinho':'Bentinho, podemos conversar um pouco? Quero ajudar a cidade. Como estão Capitu e Escobar?',
          'capitu':'Capitu, como tem passado? Ouço comentários sobre Bentinho e Escobar. O que você acha disso?',
          'escobar':'Escobar, ouvi que você e Bentinho estudaram juntos. Ainda são próximos? Pode me ajudar a entender esses ciúmes?',
          'bacamarte':'Doutor, como anda Bentinho? Preciso de sua ajuda para entender o que se passa, sem espalhar boatos.'}.get(npc,'Boa tarde. Quero ouvir sua opinião sobre a cidade e os comentários sobre Capitu, Bentinho e Escobar. Quem pode me ajudar?')
        result={'npc_id':npc,'question':question,'kind':'real_provider_probe','status':'pending'}
        started=monotonic()
        try:
            async with sim.gate.hold(sim.game_id):
                reply=await harness.respond(sim.game_id,npc,conversation.id,'player',question)
            result.update(status='completed',reply=reply.message.content)
        except Exception as exc:
            result.update(status='failed',error_code=getattr(exc,'code',type(exc).__name__))
        result['usage']=(await usage.summary(sim.game_id)).model_dump(mode='json')
        result['runtime_seconds']=round(monotonic()-started,3)
        await client.aclose();await redis.aclose()
        with path.open('a') as stream: stream.write(json.dumps(result,ensure_ascii=False,default=str)+'\n')
        print('live',npc,result['status'],flush=True)
        if result.get('error_code') in {'llm_credentials_missing','llm_credentials_unavailable','llm_authentication_failed'}:
            print('Credenciais indisponíveis; demais probes não iniciados.',flush=True)
            break

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['calibration','validation','live'],required=True)
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    asyncio.run(run_live() if args.phase=='live' else run_games(args.phase,args.limit))
