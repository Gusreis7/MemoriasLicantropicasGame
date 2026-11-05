# Partidas reais com Floriano controlado por LLM

`scripts/run_session_simulations.py` executa N partidas sequenciais contra a API
pública da aplicação em execução. Um agente LLM interpreta Floriano: escolhe onde
andar, quem abordar, o que perguntar, quais provas examinar e apresentar, quando
acusar, convocar assembleia ou pular o dia. As respostas dos NPCs, do mestre e da
convivência usam os clientes LLM reais configurados no servidor.

O runner não contém provedor offline, decisões por ranking estático, relógio
controlado, sorteio substituído nem resultados injetados. Dublês continuam restritos
a testes unitários e ao servidor de testes do navegador. Esse teste de contrato não
é uma medição de comportamento real.

## Preparar e executar

Configure as credenciais Bedrock da aplicação e de Floriano por perfil AWS ou
token de ambiente, conforme o [guia local](execucao_docker.md). Suba a aplicação:

```sh
make setup
uv run python scripts/run_session_simulations.py --help
```

Para executar dez partidas, com limite total de 200 chamadas do agente Floriano:

```sh
uv run python scripts/run_session_simulations.py --games 10 \
  --api-url http://localhost:7079 \
  --aws-profile terraform \
  --max-live-calls 200 \
  --max-steps 200 --max-seconds 1800 \
  --output artifacts/simulations/live
```

`--aws-profile` pode ser omitido quando o ambiente já fornece a credencial. O
servidor precisa de sua própria credencial válida: configurar Floriano não altera
a autenticação dos NPCs. `--preflight-only` verifica configuração e disponibilidade
sem gerar uma decisão LLM; não comprova que a inferência do provedor funcionará.
Use um diretório novo para cada execução; o runner recusa sobrescrever um resumo
existente. Sem `--output`, cria um diretório com horário da execução.

O relógio do jogo segue o servidor real. Caminhar leva tempo e respeita validações
de posição e revisão; esperar não altera o relógio artificialmente. Pular o dia é a
mesma ação pública disponível ao jogador. Falhas de API são registradas e retornam
ao agente para ele decidir o próximo passo.

## Limites e consumo

`--max-live-calls` é obrigatório e limita **somente Floriano**, somando todas as
partidas e tentativas de geração. NPCs, mestre, extração, convivência, assembleia e
editorial são executados pela aplicação e têm consumo separado. O limite do agente
não é um teto de chamadas ou de cobrança de todo o servidor. Encerrar o runner
não remove partidas nem apaga dados da aplicação.

`--max-steps` e `--max-seconds` limitam cada sessão. Ao atingir um limite, falhar a
autenticação ou esgotar chamadas, a sessão é registrada como interrompida/incompleta,
sem fabricar vitória ou derrota. A partida permanece no servidor; os serviços
normais continuam seguindo sua configuração. Use a API/Redis de uma instalação
dedicada à avaliação se desejar separar as partidas das de jogadores.

## Evidências e estatísticas

Cada partida tem seu diretório `session-NNNN`, com `events.jsonl` incremental e
`session.json`. O lote escreve `summary.json`, atualizado a cada partida, para
preservar resultados já encerrados mesmo se a próxima execução falhar.

Os eventos registram observações públicas, decisões e ações do agente, respostas,
falhas e durações reais. O relatório distingue partidas encerradas pelo motor de
sessões interrompidas, além de contar ações, erros e resultados. A medição do agente
registra chamadas, tokens fornecidos pelo provedor, latência e custo estimado quando
há preços configurados; tokens ausentes não são inventados.

Para coletar também métricas do servidor, utilize as opções `--redis-url` e
`--redis-prefix` com os valores da aplicação. Essa leitura é separada do contexto
do agente: Floriano continua recebendo apenas dados públicos. Sem acesso às métricas
do servidor, o consumo total da simulação não pode ser inferido pelo consumo de
Floriano. Não compartilhe relatórios sem revisar as transcrições que eles contêm.

O Redis do Compose não publica uma porta no host. Para usar a credencial e o Redis
da aplicação, o runner também está incluído na imagem da API:

```sh
docker compose exec -T api python scripts/run_session_simulations.py \
  --games 10 --max-live-calls 200 --api-url http://127.0.0.1:8000 \
  --redis-url redis://redis:6379/0 --output /tmp/live-evaluation
docker compose cp api:/tmp/live-evaluation artifacts/simulations/live-evaluation
```

Copie os resultados antes de recriar o container, pois `/tmp` é temporário.

## Amostras reais desta implementação

Em 05/11/2026 foram executadas duas amostras curtas contra a aplicação local e o
Qwen/Mantle real. A primeira realizou um movimento; a segunda realizou dois
movimentos, uma busca de vestígio e uma observação. Ambas pararam com
`llm_invalid_response` após duas tentativas inválidas consecutivas. Foram nove
tentativas de transporte do agente, cinco respostas aceitas e quatro falhas.
Nenhuma partida terminou e não houve diálogo com NPC nessas amostras. Isso valida
parte da interação real e o registro das falhas, não a qualidade dos diálogos ou
o comportamento de uma partida completa. Os arquivos locais estão em
`artifacts/simulations/live-smoke-20261105*`.

Os tokens das respostas rejeitadas pelo adaptador não estão disponíveis. O custo
estimado dos tokens conhecidos é parcial; `cost_complete=false` identifica essa
limitação. Métricas do servidor coletadas posteriormente são uma fotografia do
momento da coleta, pois suas partidas e convivência continuam em execução.

## Como interpretar

Compare resultados, duração, perguntas, repetição de ações, evidências utilizadas,
recusas do delegado, diálogos degradados e erros técnicos. Separe taxas de vitória
entre partidas concluídas da proporção de sessões que conseguiram terminar. Um
lote truncado pelo limite de chamadas pode favorecer apenas as primeiras partidas;
registre o limite junto com a amostra e não trate partidas incompletas como derrota.

O agente vê casos, cenários, elenco e mensagens públicas, sem papéis secretos ou
memórias privadas dos NPCs. Sua interpretação pode falhar, insistir ou desconfiar
sem fundamento; esses comportamentos pertencem ao resultado da avaliação. Uma
partida que terminou por fallback técnico não comprova qualidade narrativa.

As antigas políticas determinísticas e o relatório offline de dez partidas foram
retirados do checkout. Seu histórico está no Git. Não há resultados reais novos
implícitos nesta documentação: cada avaliação exige executar o loop e examinar os
artefatos gerados.
