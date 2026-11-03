"""100 cenários pareados antes/depois, cada um com diálogo Qwen e partida programada.

PYTHONPATH=src:scripts .venv/bin/python scripts/benchmark_investigation_v3.py --phase before --source-root /tmp/ml-v3-baseline
PYTHONPATH=src:scripts .venv/bin/python scripts/benchmark_investigation_v3.py --phase after --source-root .
Checkpoint por case_id; --limit1 permite conferir a inicialização sem repetircenários.
"""
import argparse,asyncio,json,sys,statistics,re
from pathlib import Path
from time import monotonic
from uuid import UUID,NAMESPACE_URL,uuid5
from decimal import Decimal

parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['before','after'],required=True)
parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--limit',type=int,default=100)
parser.add_argument('--concurrency',type=int,default=3);parser.add_argument('--offline',action='store_true')
parser.add_argument('--output',type=Path,default=Path('docs/exploracao_investigacao_v3'))
args=parser.parse_args();source=args.source_root.resolve()
sys.path.insert(0,str(source/'src'));sys.path.insert(1,str(source/'scripts'))
import fakeredis
from explore_narrative_balance import NarrativeSimulation,IDS
from simulate_gameplay import rank_suspects
from memorias_licantropicas.contracts.model import Conversation,LLMResponse,GameState,GameCharacter
from memorias_licantropicas.contracts.errors import ConflictError,AccessDeniedError
from memorias_licantropicas.modules.agents.service import HarnessService
from memorias_licantropicas.modules.session_master.service import SessionMasterService
from memorias_licantropicas.modules.knowledge.service import KnowledgeService
from memorias_licantropicas.infrastructure.usage import RedisUsageRepository,MeteredLLMClient,UsagePricing
from memorias_licantropicas.infrastructure.llm.bedrock_mantle import BedrockMantleClient
from memorias_licantropicas.infrastructure.llm.aws_credentials import ProfileTokenProvider
from memorias_licantropicas.settings import Settings

POLICIES=('informed','common_rush','unexamined','single_source','informed')
QUESTIONS=('help','relations','alibi','object','followup')
STOP={'a','o','as','os','de','da','do','das','dos','em','na','no','que','com','por','para','um','uma','e','se','eu','voce','ele','ela','isso','floriano','detetive','mais','como','mas','quando','tem','pode','sobre','nao','sao'}

def terms(text):
    import unicodedata
    text=''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))
    return {w for w in re.findall(r'[a-z]+',text) if len(w)>3 and w not in STOP}

def quality_metrics(text,authorized):
    lowered=text.casefold();tokens=terms(text)
    anchors=set()
    for fact in authorized:
        overlap=tokens & terms(fact)
        if len(overlap)>=2:anchors.update(overlap)
    evasive=bool(re.search(r'prefiro não|não posso dizer|nada a declarar|não tenho nada|não insista|não me cabe|não posso confirmar',lowered))
    metaphor=bool(re.search(r'sombra|espelho|labirinto|maré|silêncio|escuridão|coração|romance|capítulo|vento|poesia|enigma',lowered))
    lead=bool(re.search(r'pergunt|procure|converse|fale com|pode confirmar|confirmar com|vi |ouvi |seminário|medica|tratamento|capitu e escobar são amigos|ciúme',lowered))
    return {'words':len(text.split()),'authorized_anchor_count':len(anchors),'actionable_proxy':bool(len(anchors)>=2 and (lead or not metaphor) and not evasive),
        'evasive_proxy':evasive,'metaphor_proxy':metaphor,'named_next_step':bool(re.search(r'(pergunt|procure|converse|fale com).{0,50}(Capitu|Bentinho|Escobar|Bacamarte|Rubião|Virgília|Florença)',text,re.I))}

class OfflineLLM:
    async def complete(self,messages):
        if 'mestre privado' in messages[0].content:return LLMResponse(content='{"kind":"conversation"}',model='offline')
        return LLMResponse(content='Capitu e Bentinho são casados. Pergunte a Capitu sobre o ciúme dele.',model='offline')

class EvaluationSimulation(NarrativeSimulation):
    async def create(self,wolf):
        profiles=await self.catalog.list()
        game=GameState(id=getattr(self,'fixture_game_id',uuid5(NAMESPACE_URL,f'v3-fixture:{self.seed}')),
            created_at=self.clock(),content_version=self.catalog.content_version,
            characters=tuple(GameCharacter(character_id=p.id,role='werewolf' if p.id==wolf else 'civil') for p in profiles))
        assert await self.games.create(game)
        self.game_id=game.id
        return await self.investigation.get(game.id)
    async def probe(self,index,persona,judge,usage):
        actor=IDS[(index//7)%len(IDS)]
        kind=QUESTIONS[index%len(QUESTIONS)]
        profile=await self.catalog.get(actor)
        conversation=Conversation(id=uuid5(NAMESPACE_URL,f'v3:{index}:thread'),game_id=self.game_id,
            participant_ids=('player',actor),created_at=self.clock())
        await self.memory.create_conversation(conversation)
        case=await self.investigation.get(self.game_id)
        if kind in ('object','followup'):
            case=await self.collect(case)
            from memorias_licantropicas.modules.world.catalog import LOCATIONS
            for loc in LOCATIONS:
                snap=await self.walk_to(loc.id,160)
                npc=next((n for n in snap.visible_npcs if n.npc_id==actor),None)
                if npc:
                    await self.walk_to(loc.id,npc.x)
                    case=await self.investigation.present(self.game_id,case.inventory[0].id,actor)
                    break
        if kind=='relations':
            social=await self.social_repository.get(self.game_id)
            relations=tuple(r.model_copy(update={'trust':20,'affinity':12,'resentment':0})
                if r.actor_id==actor and r.target_id=='player' else r for r in social.relationships)
            assert await self.social_repository.save(social.model_copy(update={'revision':social.revision+1,'relationships':relations}),social.revision)
        questions={
            'help':'Quero ajudar a cidade. Conte uma coisa concreta que você sabe sobre os moradores e diga com quem devo falar para entender melhor.',
            'relations':'O que você sabe sobre Capitu, Bentinho e Escobar? Quero entender as amizades e o ciúme, com clareza.',
            'alibi':'Onde estava na noite em que Brás Cubas morreu? Com quem estava, e quem pode esclarecer isso?',
            'object':'Mostrei esse objeto. O que você consegue me dizer concretamente sobre ele, e quem mais pode reconhecer?',
            'followup':'Ainda não entendi. Pode ser direto sobre esse objeto: o que sabe e qual pergunta devo fazer a seguir?'}
        if kind=='relations':
            questions['relations']={
                'capitu':'Além do ciúme de Bentinho, o que você deseja para sua própria vida? Pode falar com franqueza comigo.',
                'escobar':'O que sua amizade com Bentinho significa para você desde o seminário? Pode contar com minha discrição.',
                'bentinho':'Como vai o acompanhamento com Bacamarte? O que o incomoda no tratamento?',
                'bacamarte':'Quero entender o acompanhamento de Bentinho. O que posso fazer para ajudar?',
                'florenca':'Seu pai continua na Casa Verde? Conte o que aconteceu e como posso ajudar.',
                'rubiao':'Sua dedicação a Florença é correspondida? Pode falar comigo com franqueza.',
                'virgilia':'Como anda Florença? Quero ouvir sobre a amizade de vocês e como Rubião a trata.',
            }[actor]
        knowledge=KnowledgeService(self.social_repository,self.catalog,judge,clock=self.clock)
        master=SessionMasterService(self.turns,self.games,self.memory,judge,self.redis,self.prefix)
        harness=HarnessService(self.catalog,self.games,self.memory,persona,day_policy=self.turns,
            context_provider=self.investigation.npc_context_locked,knowledge_provider=knowledge.context,session_master=master)
        observation=await self.investigation.npc_context_locked(self.game_id,actor)
        memory=await knowledge.context(self.game_id,actor)
        authorized=[r.get('conteudo','') for r in memory.get('memorias_relevantes',()) if r.get('visibilidade','public')=='public']
        authorized += list(memory.get('confidencias_autorizadas',()))
        authorized += [r.get('lembranca','') for r in observation.get('suas_atividades',())]
        authorized += [r.get('fala','') for r in observation.get('seus_depoimentos_registrados',())]
        started=monotonic();result={'actor':actor,'question_type':kind,'question':questions[kind],'programmed_prior_trust':kind=='relations','authorized_supports':authorized}
        try:
            async with self.gate.hold(self.game_id):
                reply=await harness.respond(self.game_id,actor,conversation.id,'player',questions[kind])
            result.update(status='completed',reply=reply.message.content,**quality_metrics(reply.message.content,authorized))
        except Exception as exc:
            result.update(status='failed',error_code=getattr(exc,'code',type(exc).__name__))
        state=await self.turns.sync(self.game_id)
        result['assessments']=[e['assessment'] for e in state.dialogue_events]
        result['achievements']=[a.id for a in getattr(state,'achievements',())]
        result['usage']=(await usage.summary(self.game_id)).model_dump(mode='json')
        result['latency_seconds']=round(monotonic()-started,3)
        return result
    async def finish_game(self,policy,case):
        first_accept=None;denials=0;wrong_arrests=0;errors=[]
        for _ in range(8):
            if case.status!='active':break
            try:
                case=await self.collect(case)
                if policy=='informed' and hasattr(self.investigation,'inspect'):
                    for item in case.inventory:
                        if not getattr(item,'examined',False):case=await self.investigation.inspect(self.game_id,item.id)
                case,living=await self.survey(case)
                ranked=rank_suspects(case,living-set(case.expelled_npc_ids))
                top=ranked[0] if ranked else None
                if top:
                    evidences=tuple(e.id for e in case.inventory if policy!='common_rush' or e.kind=='common')
                    testimonies=tuple(t.id for t in case.testimonies if any(e.id==t.evidence_id for e in case.inventory if e.id in evidences))
                    if policy=='single_source' and testimonies:
                        chosen=next(t.witness_id for t in case.testimonies if t.id==testimonies[0])
                        testimonies=tuple(t.id for t in case.testimonies if t.witness_id==chosen and t.id in testimonies)
                    before=case.day
                    case=await self.investigation.accuse(self.game_id,top['npc_id'],evidences,testimonies)
                    accepted=case.accusations[-1].accepted
                    if accepted:
                        first_accept=first_accept or before
                        real=next(m.character_id for m in (await self.games.get(self.game_id)).characters if m.role=='werewolf')
                        wrong_arrests+=int(real!=top['npc_id'])
                    else:denials+=1
                if case.status=='active':case=await self.next_morning()
            except (ConflictError,AccessDeniedError) as exc:
                errors.append(type(exc).__name__+':'+str(exc));case=await self.next_morning()
        return {'result':case.status,'method':case.ending.method if case.ending else None,'day':case.day,
            'first_accepted_day':first_accept,'refusals':denials,'wrong_arrests':wrong_arrests,'errors':errors,
            'clues':len(case.inventory),'testimonies':len(case.testimonies),'achievements':[a.id for a in getattr(case,'achievements',())]}

async def main():
    output=args.output;output.mkdir(parents=True,exist_ok=True);path=output/f'{args.phase}.jsonl'
    prior=[json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
    done={r['case_id'] for r in prior};settings=Settings()
    baseline_path=output/'before.jsonl'
    baseline={r['case_id']:r for r in (json.loads(s) for s in baseline_path.read_text().splitlines())} if baseline_path.exists() else {}
    def raw(limit):
        if args.offline:return OfflineLLM()
        return BedrockMantleClient(base_url=settings.mantle_base_url,api_key=settings.bedrock_api_key.get_secret_value() if settings.bedrock_api_key else None,
            model=settings.bedrock_model,timeout_seconds=20,max_tokens=limit,
            token_provider=ProfileTokenProvider(settings.aws_profile,settings.aws_region) if settings.aws_profile else None)
    persona_raw,judge_raw=raw(240),raw(640)
    semaphore=asyncio.Semaphore(args.concurrency)
    async def one(index):
        if index in done:return
        async with semaphore:
            redis=fakeredis.FakeAsyncRedis(decode_responses=True)
            sim=EvaluationSimulation(redis,f'v3:{args.phase}:{index}',73000+index)
            if args.phase=='after' and index in baseline:
                sim.fixture_game_id=UUID(baseline[index]['dialogue']['usage']['game_id'])
            started=monotonic();result={'case_id':index,'seed':73000+index,'phase':args.phase,'wolf':IDS[index%len(IDS)],'policy':POLICIES[index%5],'provider':'offline' if args.offline else settings.bedrock_model}
            try:
                case=await sim.create(result['wolf']);await sim.seed_social()
                usage=RedisUsageRepository(redis,sim.prefix,pricing=UsagePricing(model=settings.bedrock_model,
                    input_usd_per_million=settings.llm_input_usd_per_million,output_usd_per_million=settings.llm_output_usd_per_million,
                    source=settings.llm_pricing_source,checked_at=settings.llm_pricing_checked_at))
                persona=MeteredLLMClient(persona_raw,usage,configured_model=settings.bedrock_model)
                judge=MeteredLLMClient(judge_raw,usage,configured_model=settings.bedrock_model)
                result['dialogue']=await sim.probe(index,persona,judge,usage)
                result['game']=await sim.finish_game(result['policy'],await sim.investigation.get(sim.game_id))
                result['status']='completed'
            except Exception as exc:
                result.update(status='error',error=type(exc).__name__,detail=str(exc))
            finally:await redis.aclose()
            result['runtime_seconds']=round(monotonic()-started,3)
            with path.open('a') as f:f.write(json.dumps(result,ensure_ascii=False,default=str)+'\n')
            print(args.phase,index,result['status'],result.get('dialogue',{}).get('status'),result.get('game',{}).get('result'),flush=True)
            if result['status']=='error':raise RuntimeError('Erro inesperado registrado; interromper para investigar.')
    try:
        await asyncio.gather(*(one(i) for i in range(min(100,args.limit))))
    finally:
        for client in (persona_raw,judge_raw):
            if hasattr(client,'aclose'):await client.aclose()

asyncio.run(main())
