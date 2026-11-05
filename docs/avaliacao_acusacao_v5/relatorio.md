# Acusação v5: corrigir o bloqueio do dossiê de Bentinho

## Diagnóstico e reprodução

O dossiê relatado pelo jogador foi reconstruído com os seis tipos de objeto e as cópias repetidas, sem exame: dois exclusivos (rosário e papel Santiago), um singular e três comuns, com Florença e Bacamarte reconhecendo os dois exclusivos. O motor anterior somava **8,5 pontos** e reconhecia as duas fontes, mas recusava somente pelo requisito absoluto de exame. O agrupamento não era o causador: uma cópia examinada já atendia à mesma espécie. O bloqueio era da regra, somado à limitação de uma tentativa por dia inclusive após recusa.

A reprodução foi recusada antes e aceita depois, por `corroborated_personal_marks`. Os arquivos `reproducao_antes.json` e `reproducao_depois.json` preservam a decisão e a explicação. Os testemunhos são gerados pelo motor a partir do cenário equivalente; não se trata de uma cópia de toda a transcrição fornecida pelo jogador.

## Regras entregues

- A rota anterior continua válida: exclusivo examinado, pelo menos dois tipos, pontuação mínima 5 e duas fontes externas, ou uma fonte e contradição pública de álibis.
- Nova rota: **dois tipos exclusivos diferentes**, cada um reconhecido por **duas testemunhas externas distintas**, justificam a custódia sem exame adicional. Duplicatas do mesmo objeto não substituem dois tipos; a mesma pessoa repetida não vira outra fonte. Reconhecimentos de comuns não servem como corroboração das marcas exclusivas.
- Comuns continuam em 0,25 por tipo, teto conjunto 0,5; singulares em 1, teto 2; exclusivos em 3. A nova rota não lê papel secreto, autoria real do crime, sentimentos ou veracidade privada do depoente. Custódia ainda precisa da confirmação noturna para vitória.
- Uma recusa permite complementar ou examinar o dossiê e reapresentá-lo no mesmo dia. Repetir imediatamente o mesmo dossiê recusado é idempotente: não gera outro registro, evento ou revisão. O relógio do jogo continua correndo.
- O delegado ganha **Conferir dossiê**, com resposta prévia do motor sobre a seleção atual. A conferência não registra acusação ou muda o prazo do dia. A seleção de provas é preservada ao reapresentar. Recusas antigas em saves não bloqueiam o novo pedido.
- Endpoint `POST /games/{game_id}/accusations/review`: `ready`, `route`, `missing`, `reason`. O campo privado de impressão do dossiê não aparece no caso público.

## Comparação de 100 partidas antes e 100 depois

| Política programada | Vitórias antes | Vitórias depois | Mediana do primeiro dia de prisão antes → depois |
| --- | --- | --- | --- |
| Examina objetos e ouve fontes | 20/20 | 20/20 | 2.5 → 2.5 |
| Relatos e exclusivos, sem exame | 0/20 | 18/20 | — → 3.0 |
| Somente comuns | 0/20 | 0/20 | — → — |
| Uma fonte por acusação | 0/20 | 0/20 | — → — |
| Completa o dossiê após recusa | 20/20 | 20/20 | 3.0 → 2.0 |

As 20 partidas que examinam provas mantiveram sua viabilidade; a mudança abriu uma segunda rota coerente para depoimentos fortes. A estratégia de reapresentação teve 20 bloqueios diários antes e nenhum depois; a prisão passou da mediana do dia 3 para o dia 2. Não houve prisão da pessoa errada nestes 200 cenários. Isso não garante que nenhuma prisão errada seja possível no jogo: a mecânica do homicídio civil continua existindo.

Duas partidas sem exame ainda perderam (casos 11/Virgília e 31/Rubião): não reuniram a combinação de duas marcas corroboradas exigida pela nova rota. A condição alternativa não deve virar vitória automática com objetos repetidos ou fontes insuficientes. Examinar uma pista continua sendo outra possibilidade.

## Método e limites

Baseline 026a3c3 e regras posteriores congeladas em 478d9da. São 100 pares com os mesmos papéis, sementes, IDs de partida, plano civil e política programada. Todos consultam as projeções públicas e praticam busca, apresentação, exame quando previsto, acusação e passagem de noite pelos serviços reais. Fakeredis usa namespaces exclusivos e não acessa as partidas do usuário.

Os papéis sorteados são controlados pela fixture para cobrir os sete personagens; a política escolhe suspeitos somente por vestígios e depoimentos públicos. A auditoria de prisão errada compara o resultado com o papel conhecido da fixture. Cada política tem 20 casos; há repetição de personagens e cenários relacionados. O resultado não estima taxa de vitória de humanos nem confiança estatística de equilíbrio geral. As políticas fracas são controles negativos deliberados, não um grupo aleatório de jogadores.

`rework` tenta uma acusação incompleta uma vez quando aparece uma peça pessoal, depois examina e corrige; permite medir o impedimento diário anterior. `witness_first` nunca usa o exame; `one_source` anexa depoimentos de somente uma pessoa por acusação. Não foram simuladas novas falas livres ou mudança de personalidade do modelo.

**Custo de inferência: US$ 0; chamadas Qwen/AWS: 0.** A avaliação testa as regras, interfaces de serviço e caminhos de partida. As duas centenas de linhas originais e seus hashes estão preservados; os resultados não foram substituídos por novas tentativas.

## Reproduzir

```sh
PYTHONPATH=.:scripts .venv/bin/python scripts/benchmark_accusation_v5.py --phase before --source-root /tmp/checkout-026a3c3 --output /tmp/nova-avaliacao
PYTHONPATH=.:scripts .venv/bin/python scripts/benchmark_accusation_v5.py --phase after --source-root . --output /tmp/nova-avaliacao
.venv/bin/python scripts/report_accusation_v5.py
```

O benchmark recusa sobrescrever uma rodada já arquivada. O gerador do relatório lê os JSONL em `docs/avaliacao_acusacao_v5`. Os testes de contrato cobrem a mesma avaliação sem mutação, a reapresentação no mesmo dia, agrupamento e ausência de leitura da verdade oculta.

## Validação da entrega (2026-11-04)

- 730 testes de backend passaram no workspace integrado; 56 de frontend e build TypeScript/Vite passaram.
- 51 testes de regras/API/persistência também passaram com Redis real, em namespaces isolados.
- 15 fluxos passaram no Brave, incluindo os dois novos cenários de dossiê agrupado e reapresentação no mesmo dia.
- Aplicação reconstruída em Docker e servida nas portas locais 7077/7078/7079.
- As alterações já preparadas pelo usuário no index foram preservadas byte a byte durante a integração.
