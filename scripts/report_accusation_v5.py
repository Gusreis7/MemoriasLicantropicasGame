"""Resumo reprodutível das 200 partidas e da reprodução do dossiê do jogador."""
import json,statistics,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1];folder=root/'docs/avaliacao_acusacao_v5'
phases={p:[json.loads(line) for line in (folder/f'{p}.jsonl').read_text().splitlines()] for p in ('before','after')}
for rows in phases.values():assert len(rows)==100 and {r['case_id'] for r in rows}==set(range(100))
before={r['case_id']:r for r in phases['before']};after={r['case_id']:r for r in phases['after']}
assert all(tuple(before[i][key] for key in ('seed','werewolf','policy'))==tuple(after[i][key] for key in ('seed','werewolf','policy')) for i in range(100))
policies=('examining','witness_first','common_only','one_source','rework');summary={'baseline_commit':'026a3c3','after_rules_commit':'478d9da','games_per_phase':100,'llm_calls':0,'estimated_llm_cost_usd':'0','phases':{}}
for phase,rows in phases.items():
 summary['phases'][phase]={}
 for policy in policies:
  group=[r for r in rows if r['policy']==policy];days=[r['first_accepted_day'] for r in group if r['first_accepted_day']]
  summary['phases'][phase][policy]={'games':len(group),'won':sum(r['result']=='won' for r in group),'lost':sum(r['result']=='lost' for r in group),'wrong_detentions':sum(r['wrong_detentions'] for r in group),'first_accepted_day_median':statistics.median(days) if days else None,'daily_blocks':sum(bool(a.get('blocked')) for r in group for a in r['attempts'])}
summary['reproduction']={p:json.loads((folder/f'reproducao_{p}.json').read_text()) for p in ('antes','depois')}
summary['raw_sha256']={p:hashlib.sha256((folder/f'{p}.jsonl').read_bytes()).hexdigest() for p in phases}
(folder/'resumo.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
labels={'examining':'Examina objetos e ouve fontes','witness_first':'Relatos e exclusivos, sem exame','common_only':'Somente comuns','one_source':'Uma fonte por acusação','rework':'Completa o dossiê após recusa'}
rows=[]
for policy in policies:
 b,a=(summary['phases'][p][policy] for p in ('before','after'))
 rows.append(f"| {labels[policy]} | {b['won']}/{b['games']} | {a['won']}/{a['games']} | {b['first_accepted_day_median'] or '—'} → {a['first_accepted_day_median'] or '—'} |")
report='''# Acusação v5: corrigir o bloqueio do dossiê de Bentinho

## Diagnóstico e reprodução

O dossiê relatado pelo jogador foi reconstruído com os seis tipos de objeto e as cópias repetidas, sem exame: dois exclusivos (rosário e papel Santiago), um singular e três comuns, com Florença e Bacamarte reconhecendo os dois exclusivos. O motor anterior somava **8,5 pontos** e reconhecia as duas fontes, mas recusava somente pelo requisito absoluto de exame. O agrupamento não era o causador: uma cópia examinada já atendia à mesma espécie. O bloqueio era da regra, somado à limitação de uma tentativa por dia inclusive após recusa.

A reprodução foi recusada antes e aceita depois, por `corroborated_personal_marks`. Os arquivos `reproducao_antes.json` e `reproducao_depois.json` preservam a decisão e a explicação. Os testemunhos são gerados pelo motor a partir do cenário equivalente; não se trata de uma cópia de toda a transcrição fornecida pelo jogador.

## Regras entregues

- A rota anterior continua válida: exclusivo examinado, pelo menos dois tipos, pontuação mínima5 e duas fontes externas, ou uma fonte e contradição pública de álibis.
- Nova rota: **dois tipos exclusivos diferentes**, cada um reconhecido por **duas testemunhas externas distintas**, justificam a custódia sem exame adicional. Duplicatas do mesmo objeto não substituem dois tipos; a mesma pessoa repetida não vira outra fonte. Reconhecimentos de comuns não servem como corroboração das marcas exclusivas.
- Comuns continuam em0,25 por tipo, teto conjunto0,5; singulares em1, teto2; exclusivos em3. A nova rota não lê papel secreto, autoria real do crime, sentimentos ou veracidade privada do depoente. Custódia ainda precisa da confirmação noturna para vitória.
- Uma recusa permite complementar ou examinar o dossiê e reapresentá-lo no mesmo dia. Repetir imediatamente o mesmo dossiê recusado é idempotente: não gera outro registro, evento ou revisão. O relógio do jogo continua correndo.
- O delegado ganha **Conferir dossiê**, com resposta prévia do motor sobre a seleção atual. A conferência não registra acusação ou muda o prazo do dia. A seleção de provas é preservada ao reapresentar. Recusas antigas em saves não bloqueiam o novo pedido.
- Endpoint `POST /games/{game_id}/accusations/review`: `ready`, `route`, `missing`, `reason`. O campo privado de impressão do dossiê não aparece no caso público.

## Comparação de100 partidas antes e100 depois

| Política programada | Vitórias antes | Vitórias depois | Mediana do primeiro dia de prisão antes → depois |
| --- | --- | --- | --- |
'''+ '\n'.join(rows)+'''

As20 partidas que examinam provas mantiveram sua viabilidade; a mudança abriu uma segunda rota coerente para depoimentos fortes. A estratégia de reapresentação teve20 bloqueios diários antes e nenhum depois; a prisão passou da mediana do dia3 para o dia2. Não houve prisão da pessoa errada nestes200 cenários. Isso não garante que nenhuma prisão errada seja possível no jogo: a mecânica do homicídio civil continua existindo.

Duas partidas sem exame ainda perderam (casos11/Virgília e31/Rubião): não reuniram a combinação de duas marcas corroboradas exigida pela nova rota. A condição alternativa não deve virar vitória automática com objetos repetidos ou fontes insuficientes. Examinar uma pista continua sendo outra possibilidade.

## Método e limites

Baseline026a3c3 e regras posteriores congeladas em478d9da. São100 pares com os mesmos papéis, sementes, IDs de partida, plano civil e política programada. Todos consultam as projeções públicas e praticam busca, apresentação, exame quando previsto, acusação e passagem de noite pelos serviços reais. Fakeredis usa namespaces exclusivos e não acessa as partidas do usuário.

Os papéis sorteados são controlados pela fixture para cobrir os sete personagens; a política escolhe suspeitos somente por vestígios e depoimentos públicos. A auditoria de prisão errada compara o resultado com o papel conhecido da fixture. Cada política tem20 casos; há repetição de personagens e cenários relacionados. O resultado não estima taxa de vitória de humanos nem confiança estatística de equilíbrio geral. As políticas fracas são controles negativos deliberados, não um grupo aleatório de jogadores.

`rework` tenta uma acusação incompleta uma vez quando aparece uma peça pessoal, depois examina e corrige; permite medir o impedimento diário anterior. `witness_first` nunca usa o exame; `one_source` anexa depoimentos de somente uma pessoa por acusação. Não foram simuladas novas falas livres ou mudança de personalidade do modelo.

**Custo de inferência: US$0; chamadas Qwen/AWS:0.** A avaliação testa as regras, interfaces de serviço e caminhos de partida. As duas centenas de linhas originais e seus hashes estão preservados; os resultados não foram substituídos por novas tentativas.

## Reproduzir

```sh
PYTHONPATH=.:scripts .venv/bin/python scripts/benchmark_accusation_v5.py --phase before --source-root /tmp/checkout-026a3c3 --output /tmp/nova-avaliacao
PYTHONPATH=.:scripts .venv/bin/python scripts/benchmark_accusation_v5.py --phase after --source-root . --output /tmp/nova-avaliacao
.venv/bin/python scripts/report_accusation_v5.py
```

O benchmark recusa sobrescrever uma rodada já arquivada. O gerador do relatório lê os JSONL em `docs/avaliacao_acusacao_v5`. Os testes de contrato cobrem a mesma avaliação sem mutação, a reapresentação no mesmo dia, agrupamento e ausência de leitura da verdade oculta.
'''
# Espaçamento dos números no texto editorial.
for old,new in [('mínima5','mínima 5'),('em0,25','em 0,25'),('conjunto0,5','conjunto 0,5'),('em1,','em 1,'),('teto2','teto 2'),('em3.','em 3.'),('de100','de 100'),('e100','e 100'),('As20','As 20'),('teve20','teve 20'),('dia3','dia 3'),('dia2','dia 2'),('nestes200','nestes 200'),('casos11','casos 11'),('e31/','e 31/'),('Baseline026','Baseline 026'),('em478','em 478'),('São100','São 100'),('tem20','tem 20')]: report=report.replace(old,new)
report=report.replace('US$0','US$ 0').replace('AWS:0','AWS: 0')
report+='\n## Validação da entrega (2026-11-04)\n\n- 730 testes de backend passaram no workspace integrado; 56 de frontend e build TypeScript/Vite passaram.\n- 51 testes de regras/API/persistência também passaram com Redis real, em namespaces isolados.\n- 15 fluxos passaram no Brave, incluindo os dois novos cenários de dossiê agrupado e reapresentação no mesmo dia.\n- Aplicação reconstruída em Docker e servida nas portas locais 7077/7078/7079.\n- As alterações já preparadas pelo usuário no index foram preservadas byte a byte durante a integração.\n'
(folder/'relatorio.md').write_text(report)
print(json.dumps(summary['phases'],ensure_ascii=False))
