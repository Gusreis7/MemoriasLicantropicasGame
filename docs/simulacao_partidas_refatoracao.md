# Partidas completas para validar a refatoração LLM

## Execução

```sh
uv run python scripts/run_session_simulations.py --games 100 --seed 20261105
uv run pytest tests/test_session_simulations.py -q
```

O modo padrão é **offline**. Ele não lê perfis AWS, não cria cliente Mantle e não
faz inferência paga. `--redis-url` permite testar a mesma persistência em um Redis
real; sem essa opção, usa FakeAsyncRedis. Cada execução reserva um prefixo único,
limpa apenas suas próprias chaves e nunca executa FLUSHDB/FLUSHALL.

Para testar o provedor real, a opção é deliberadamente explícita:

```sh
uv run python scripts/run_session_simulations.py --live --games 1 \
  --aws-profile terraform --max-live-calls 100 \
  --output artifacts/simulations/session-live.json
```

O perfil e a cota são obrigatórios no modo real. A cota é compartilhada por todas
as personas, mestre, extrator, conversas sociais e editorial, inclusive reparos.
Seu esgotamento impede a chamada antes do transporte e aparece no relatório;
a partida pode continuar com os fallbacks e erros do motor. Essas partidas
continuam usando um relógio controlado e uma política automatizada, não medem
latência humana nem o comportamento de jogadores reais.

## O que efetivamente executa

- `GameService.create`: sorteio e criação verdadeiros, sem inserir manualmente
  um GameState com o culpado escolhido pelo investigador.
- `WorldService`: viagens, intenção de movimento, aproximação e reserva/soltura
  do NPC. O relógio contabiliza deslocamento; não há teleporte de coordenadas.
- `ConversationService` e `HarnessService`: diálogo pelo grafo LangGraph,
  parsing, revisão pelo mestre, guarda e persistência. Cada resposta retornada
  é procurada novamente no histórico público para verificar o commit.
- `KnowledgeService` e `SocialService`: extração de alegações, proveniência,
  agendamento, caminhada dos moradores, falas entre NPCs e memória social.
- `InvestigationService`: busca, exame, apresentação de objetos, depoimentos,
  revisão do dossiê, prisão ou assembleia curta com réplica. Álibis são perguntados
  em linguagem natural e registrados pelo mestre durante o diálogo; o runner não
  chama o endpoint separado de interrogatório para fabricar esse registro.
- `TurnService`: anoitecer, crimes ou noites poupadas, transformação/soltura,
  novas manhãs e vitória/derrota decididas pelas regras reais.

Os mesmos serviços usados pelo servidor são compostos no runner. O único dublê
narrativo é o provedor offline, que lê exclusivamente o prompt projetado para cada
papel. Ele responde com citações de fatos já autorizados; não conhece o repository
de partidas nem consulta a identidade dos demais. As respostas estruturadas passam
pelos mesmos parsers e validações que as do Mantle.

## Políticas, sementes e falhas

`investigator` compara peças distintas e depoimentos públicos e consulta a revisão
do delegado antes de acusar. `assembly` apresenta o mesmo dossiê em debate público
quando há sustentação; se não houver solução, continua investigando. `rash` pode
acusar antes de o dossiê ser aceito. `passive` conversa e observa a cidade, mas não
acusa: deve perder após noites efetivamente resolvidas.

A classificação de suspeitos recebe somente `CasePublic`, moradores vistos e
relatos com atribuição. Repetir um mesmo tipo de item não aumenta sua pontuação.
A identidade do lobisomem só entra na auditoria **depois** do estado terminal. O
fixture controla as fontes de entropia/relógio: sorteio em GameService, UUID da
partida e sementes das noites. Nenhuma regra de vitória, pista, voto ou condenação
é substituída. Como esses pontos de entropia usam patches de fixture, as execuções
são serializadas para impedir mistura de sementes entre partidas concorrentes.

A bateria intercala JSON inválido uma vez, JSON sempre inválido e falha de
autenticação, além de partidas sem injeção de falhas. São testadas recuperação
limitada, preservação de rascunho/histórico e continuidade das mecânicas. Uma partida
que não alcançar um resultado terminal em 16 ciclos é falha do runner, nunca
convertida artificialmente em derrota ou vitória.

## Resultados e limites

O relatório completo registra ações por dia, rankings públicos, chamadas por
papel, eventos do grafo, mensagens persistidas, encontros entre moradores, consumo
e resultado final. Logs não incluem prompts privados nem credenciais. A evidência
compacta da bateria de 100 partidas fica em `docs/reports/session_refactor_100.json`.

Tokens no modo offline são **aproximações por contagem de caracteres**, não saídas
do tokenizer Qwen. O custo AWS real é zero. No modo real, somente metadados do
provedor alimentam a estimativa de tabela; faturamento real fica desconhecido,
separado da estimativa. Uma aprovação offline demonstra execução dos fluxos e
contratos, não fluência, qualidade literária, resistência semântica a ataques ou
balanceamento validado com o Qwen.

O runner anterior `scripts/simulate_gameplay.py` é mantido porque benchmarks e
regressões históricos importam sua classe `Simulation`. Ele cobre um experimento
anterior de regras e amostras narrativas separadas. O novo runner é o caminho para
exercitar partidas e a orquestração integrada; relatórios antigos não foram
reescritos como se tivessem usado LangGraph.
