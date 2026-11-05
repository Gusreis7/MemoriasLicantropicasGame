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

Os mesmos serviços usados pelo servidor são compostos no runner. O deslocamento
consome distância/210 segundos; busca e apresentação consomem um segundo, uma fala
dois segundos e viagem pelo mapa usa a ação pública sem custo temporal adicional.
O modelo offline não consome latência virtual de inferência. Essas hipóteses de
agenda fazem parte do experimento e não representam o tempo de um jogador humano.
 O único dublê
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


### Bateria executada na árvore integrada

Foram executadas **100 partidas completas**, todas encerradas pelo motor: **75
vitórias e 25 derrotas**. As 25 partidas passivas terminaram em derrota; cada uma
das três políticas ativas venceu suas 25 partidas. Os sete personagens apareceram
como lobisomem: Capitu 16, Bacamarte 16, Virgília 7, Escobar 18, Rubião 15,
Florença 15 e Bentinho 13. As partidas duraram de 2 a 9 dias.

| Caminho efetivamente exercitado | Quantidade |
| --- | ---: |
| Invocações do grafo de diálogo | 2.493 |
| Diálogos com geração/revisão concluída | 2.011 |
| Respostas de fallback explícito | 292 |
| Erros de autenticação sem resposta gerada | 190 |
| Álibis registrados por diálogo natural | 952 |
| Encontros sociais / falas sociais confirmadas | 315 / 1.214 |
| Manhãs resolvidas pelo motor | 292 |
| Assembleias abertas e resolvidas | 25 |
| Acusações apresentadas ao delegado | 90 |
| Encerramentos por prisão / assembleia / sobrevivência da fera | 52 / 23 / 25 |

O máximo observado foi de **duas tentativas de geração por invocação** e uma
avaliação do mestre; o limite contratual também é testado para reparo semântico.
A bateria contém 70 partidas sem falhas, 10 com um JSON inválido, 10 com JSON
sempre inválido e 10 com autenticação recusada. As 7.425 chamadas foram ao dublê
local: **zero chamadas AWS e custo AWS real US$ 0**. Os oito testes específicos
das partidas passaram em 9,47 segundos na árvore integrada.

A política ativa visita todos os moradores disponíveis e esgota os vestígios e
depoimentos públicos. Por isso, a taxa de vitória de 100% dessas políticas **não
é evidência de balanceamento para humanos**. O resultado revela também que o
caminho determinístico de apresentação de itens permite continuar investigando
mesmo se a geração estiver indisponível. A validação demonstrou transições,
contratos, persistência e fallbacks; a avaliação narrativa com Qwen real permanece
separada e não foi executada nesta bateria.

Houve 1.226 tentativas de fala social e 1.214 mensagens sociais confirmadas. As
12 tentativas restantes não devem ser contadas como interações propagadas; o
relatório não exporta a causa individual dessas recusas. O total de 8.796 mensagens
observadas no histórico público está sujeito ao limite de 50 por consulta.
O relatório JSON registra essas limitações e verificações por partida.
