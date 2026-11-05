"""Reproduz conversas com Bedrock em namespace Redis temporário e exclusivo."""
import argparse
import asyncio
import json
import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

from src.composition import build_services
from src.contracts.model import ConversationMessage
from src.infrastructure.redis_repository import RedisMemoryRepository
from src.modules.world.gate import RedisPlayerGate
from src.settings import Settings


async def run(rounds):
    results=[]
    for number in range(rounds):
        prefix='ml:dialogue-regression:'+uuid4().hex
        services=build_services(Settings(redis_prefix=prefix,social_enabled=False))
        calls=[]
        for label,client in [('persona',services.harness._llm),('master',services.harness._session_master._llm)]:
            original=client.complete
            async def capture(prompt,original=original,label=label,*,tools=(),tool_choice=None):
                result=await original(prompt,tools=tools,tool_choice=tool_choice)
                calls.append({'stage':label,'output':result.model_dump(mode='json', include={'tool_calls','invalid_tool_calls'})})
                return result
            client.complete=capture
        memory=RedisMemoryRepository(services.redis,prefix)
        try:
            game=await services.games.create()
            await services.turns.sync(game.id)
            gate=RedisPlayerGate(services.redis,prefix,90)
            for npc,questions in [('capitu',['olá capitu','sabe se alguem teria motivos pra desgostar de bras cubas?']),
                                  ('rubiao',['olá sr','certo , voce acredita em lobisomens Rubião?','fale comigo homem'])]:
                conversation=uuid4()
                async def seed(question,reply):
                    # O harness cria a conversa no primeiro envio. Para o histórico
                    # legado, inicialize os metadados sem gerar uma resposta.
                    from src.contracts.model import Conversation
                    if await memory.get_conversation(game.id,conversation) is None:
                        await memory.create_conversation(Conversation(id=conversation,game_id=game.id,
                            participant_ids=('player',npc),created_at=datetime.now(UTC)))
                    await memory.append_messages(game.id,conversation,tuple(
                        ConversationMessage(id=uuid4(),sender_id=sender,content=text,created_at=datetime.now(UTC))
                        for sender,text in [('player',question),(npc,reply)]))
                if number:
                    legacy=('Posso lhe ajudar com isso: Eu sou casada com Bentinho; o ciúme dele tem provocado discussões. Ouça também Bentinho sobre essas discussões.'
                            if npc=='capitu' else 'Isso eu posso lhe contar: Tento aproximar-me de Florença, embora ela não corresponda. Compare esse relato com os que já anotou no caderno.')
                    await seed(questions[0],legacy)
                for index,question in enumerate(questions):
                    if npc=='rubiao' and index==1:
                        await seed('Mostro-lhe Lenço de algodão: Encontrado junto à cena: Lenço simples de algodão, sem monograma.',
                            'Já vi Dr. Bacamarte com um objeto igual. É comum na cidade; isso não prova que este seja daquela pessoa.')
                    calls.clear()
                    record={'round':number+1,'legacy_history':bool(number),'npc':npc,'question':question}
                    try:
                        async with gate.hold(game.id):
                            reply=await services.harness.respond(game.id,npc,conversation,'player',question)
                        record['reply']=reply.message.content
                        text=''.join(c for c in unicodedata.normalize('NFKD',reply.message.content.lower()) if not unicodedata.combining(c))
                        warnings=[]
                        if text.startswith(('posso lhe ajudar com isso:', 'isso eu posso lhe contar:')):
                            warnings.append('legacy_template')
                        if 'lobisomens' in question and (not any(term in text for term in ('acredit','creio','crer','crem','lenda','lobisom','duvid','nao sei')) or any(term in text for term in ('lenco','medicacao','consultas'))):
                            warnings.append('belief_not_answered')
                        if 'bras cubas' in question and any(term in text for term in ('medicacao','consultas','lenco')):
                            warnings.append('unrelated_clue')
                        record['warnings']=warnings
                    except Exception as exc:
                        record['error']=getattr(exc,'code',type(exc).__name__)
                    record['calls']=list(calls)
                    results.append(record)
                    print(json.dumps(record,ensure_ascii=False),flush=True)
        finally:
            # Só remove as chaves do prefixo aleatório criado por esta execução.
            keys=[key async for key in services.redis.scan_iter(match=prefix+':*')]
            if keys:
                await services.redis.delete(*keys)
            await services.aclose()
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Autoriza requisições reais e cobrança Bedrock.')
    parser.add_argument('--rounds',type=int,choices=range(1,4),default=2)
    args=parser.parse_args()
    if not args.live:
        parser.error('Use --live para executar com o Bedrock real.')
    results=asyncio.run(run(args.rounds))
    raise SystemExit(1 if any('error' in item or item.get('warnings') for item in results) else 0)
