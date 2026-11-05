# Memórias Licantropicas

Um jogo web de investigação e dedução social: entre relatos, suspeitas e interesses ocultos, descubra quem é o lobisomem. Inspirado no party game Lobisomem, com estética literária inspirada em Machado de Assis: ironia, narradores pouco confiáveis e observação das relações sociais.

## Começar a jogar

Pré-requisitos: Make, Docker com Compose ativo e uma credencial Bedrock configurada no perfil AWS local ou em `AWS_BEARER_TOKEN_BEDROCK` no `.env`.

```sh
make setup
```

Abra o [jogo](http://localhost:7077), o [painel admin](http://localhost:7078) ou a [API](http://localhost:7079/docs). O comando prepara a configuração local, constrói as imagens, sobe os serviços e verifica se Redis e API estão prontos. Ele preserva partidas existentes no volume Redis.

Depois da primeira subida, use `make up` para iniciar, `make down` para encerrar preservando as partidas e `make destroy` para encerrar e apagar todos os dados do Redis. Execute `make help` para ver os comandos disponíveis.

A [correção de relevância dos diálogos](docs/correcao_relevancia_dialogos.md) descreve o reparo das falas mecânicas e das pistas fora de assunto.

Para instalação, escolha de credencial, comandos de parada e solução de problemas, veja o [guia de execução com Docker](docs/execucao_docker.md). Se o Redis não iniciar, siga a seção de recuperação do guia antes de tentar outra subida.

A [limpeza e reinício local](docs/limpeza_reinicio.md) registra a retirada de compatibilidades antigas e o reset do volume. Use `make destroy` seguido de `make setup` para recomeçar sem partidas salvas.

## Agentes, grafos e simulações

A [arquitetura LLM atual](docs/refatoracao_llm.md) separa transporte Mantle, prompts de persona, contratos Pydantic e grafos LangGraph de diálogo/convivência. A geração usa **tool calling nativo**, `ChatModel.with_structured_output(method="function_calling")` e `PydanticToolsParser`: o schema vai em `tools`, separado das instruções narrativas. Não há pedido de JSON no prompt, extração de texto ou regex para recuperar uma resposta estruturada.

O bridge utiliza `tool_choice="auto"` e trata ausência de chamada como falha explícita; não promete forcing ou constrained decoding. **Esse novo fluxo ainda não foi validado ao vivo no Qwen/Mantle.** Consulte os [contratos](docs/contratos_llm_estruturados.md) e [suporte nativo e limites](docs/saida_nativa_llm.md).

A [simulação de partidas reais](docs/simulacao_partidas_refatoracao.md) usa um agente LLM para interpretar Floriano e interagir pela API pública da aplicação em execução. Os NPCs usam o LLM configurado na aplicação. Não há modo offline, política estática, relógio artificial nem resultado fabricado no runner; testes unitários continuam usando dublês isolados.

```sh
make setup
uv run python scripts/run_session_simulations.py --games 10 \
  --api-url http://localhost:7079 --max-live-calls 200 \
  --output artifacts/simulations/live
```

O limite de chamadas acima cobre **somente Floriano, incluindo tentativas**, e é compartilhado pelo lote. As chamadas dos NPCs, mestre e convivência ocorrem no servidor e geram consumo separado. Cada sessão mantém eventos incrementais, decisões, respostas, falhas e resultado; limites de passos e duração encerram a avaliação como incompleta, sem inventar um desfecho. Consulte o guia para credenciais, métricas e execução de N partidas.

## Deploy AWS

A [base de deploy com Terraform e GitHub Actions](docs/deploy_aws_terraform.md) prepara EC2, HTTPS/DNS, Redis persistente e autenticação OIDC. O guia contém as etapas manuais no Registro.br, AWS e GitHub, incluindo acesso privado ao admin e workflows de subida/destruição.

## Motivação

Este projeto nasce como um laboratório de aprendizado. O jogo oferece um cenário para explorar decisões sob informação incompleta e construir sistemas de agentes cujo comportamento possa ser observado e avaliado.

- **Agent harness:** experimentar o ciclo de execução dos agentes, seus contextos, limites e registros.
- **Teoria de jogos:** estudar cooperação, blefe, votação e incentivos entre participantes com objetivos distintos.
- **Tool calling:** permitir que agentes consultem informações e executem ações por interfaces explícitas.
- **Orquestração:** coordenar turnos, fases da partida e interações entre jogadores e agentes.

Essas são direções de estudo; as mecânicas e integrações ainda serão definidas durante o desenvolvimento.

## Decisões iniciais

- Python 3.13 e **uv** para dependências e ambiente virtual.
- **FastAPI** como API do jogo.
- API REST em **monólito modular**, com routers, schemas, services e repositories organizados por domínio.
- **Docker** e Docker Compose para executar a aplicação.
- **Redis** para memória das interações e **AWS Bedrock Mantle**, com Qwen 32B, para interpretar os NPCs.
- **Phaser 4, TypeScript e Vite** para o jogo 2D no navegador; painel admin separado.

A primeira versão visual permite andar lateralmente, viajar entre cinco locais pelo mapa, abordar os sete NPCs e conversar com suas personas, retomando o histórico. Inclui sprites animados, retratos e cenários pixel art. O painel admin autenticado mostra a verdade da partida, transcrições, grafo e eventos.

A suíte comum usa Redis em memória/real e inferência simulada. Experimentos históricos com Qwen real não validam o novo protocolo nativo de ferramentas. O ciclo já inclui crimes, dias/noites, acusação e desfechos. A convivência acrescenta encontros autônomos entre NPCs, relações direcionais e fofocas com origem rastreável.

## Planejamento

Os [interrogatórios e confrontos](docs/interrogatorios.md) registram local, companhia e atividade por período. Além da prisão confirmada à noite, é possível vencer por confissão sustentada em provas, com dificuldade própria de cada persona. Os civis colaboram conforme suas lembranças e interesses. No diálogo, abra **Interrogar e confrontar versões**; os registros ficam no caderno.

O [plano desta evolução](docs/plano_interrogatorios_equilibrio.md) define os contratos de implementação. A [simulação atual](docs/simulacao_partidas_refatoracao.md) executa partidas completas e identifica explicitamente o provedor utilizado. O [consumo por partida](docs/consumo_llm.md) aparece no admin autenticado, com tokens, chamadas e estimativa USD.

O [planejamento do projeto](docs/planejamento.md) descreve o ciclo do jogo, os módulos, o harness de agentes, a memória, as etapas de desenvolvimento e as decisões ainda em aberto.

O [plano visual aprovado](docs/planejamento_visual.md) detalha a delegação. A [entrega visual](docs/entrega_visual.md) registra o resultado, decisões, execução e validação.

A [revisão de exploração e diálogos](docs/revisao_exploracao_dialogos.md) registra cenários compactos, passagens entre locais, figurantes, parser de falas e guarda contra instruções maliciosas, com seus contratos e testes.

O [plano de investigação](docs/plano_investigacao.md) descreve o ciclo de cinco minutos, jornal, vestígios, testemunhos e acusação, além das propostas para a próxima etapa. Os [contratos do ciclo](docs/contratos_ciclo_investigacao.md) fixam as interfaces das frentes.

O [plano de convivência e fofocas](docs/plano_convivencia_fofocas.md), os [contratos compartilhados](docs/contratos_convivencia_fofocas.md) e a [entrega da convivência](docs/entrega_convivencia.md) descrevem memória social, encontros amigáveis/hostis, circulação de relatos e validação.

Os [contratos entre as frentes](docs/contratos_agentes.md) fixam as interfaces e responsabilidades. A [integração da base](docs/base_agentes.md) descreve configuração, uso e limites atuais.

## Desenvolvimento local

O código Python fica diretamente em `src/`, com imports `src.*`. O entrypoint ASGI é `src.main:app`:

```sh
uv sync --locked
uv run uvicorn src.main:app --host 127.0.0.1 --port 7079
```

O [guia de execução](docs/execucao_docker.md#desenvolvimento-fora-do-docker) contém o caminho para rodar API e Vite no host com Redis no Docker. O projeto usa a versão de Python indicada em `.python-version`; ao alterar dependências com `uv add` ou `uv add --dev`, versione também `uv.lock`.

## API inicial

- `GET /api/v1/characters`: apresentações públicas dos sete suspeitos.
- `GET /api/v1/characters/{character_id}`: apresentação de um suspeito.
- `POST /api/v1/games`: cria partida e sorteia um lobisomem; corpo opcional `{}`.
- `GET /api/v1/games/{game_id}`: estado público da partida.
- `GET /api/v1/world/locations` e `GET /api/v1/games/{game_id}/world`: locais e presenças visíveis.
- `POST /api/v1/games/{game_id}/movement` e `/travel`: comandos validados de exploração.
- `POST /api/v1/games/{game_id}/approaches`: aborda e retoma a thread do NPC próximo.
- `POST /api/v1/games/{game_id}/conversations`: abre conversa com `{"npc_id": "capitu"}`.
- `GET /api/v1/games/{game_id}/conversations/{conversation_id}`: consulta a conversa.
- `POST /api/v1/games/{game_id}/conversations/{conversation_id}/messages`: envia `{"content": "O que sabe sobre Brás Cubas?"}` e recebe a fala da persona.
- `GET /api/v1/games/{game_id}/conversations/{conversation_id}/messages`: recupera o histórico.
- `GET /api/v1/games/{game_id}/investigation`: relógio, fase, jornal, vestígios recolhidos e depoimentos.
- `GET /api/v1/games/{game_id}/social/reports`: falas que Floriano efetivamente ouviu, sem acesso a conversas privadas de NPCs.
- `POST /api/v1/games/{game_id}/crime-scenes/{crime_id}/search`: procura um vestígio próximo.
- `POST /api/v1/games/{game_id}/evidence/{evidence_id}/present`: apresenta um objeto ao NPC próximo.
- `POST /api/v1/games/{game_id}/accusations`: entrega objetos e depoimentos ao delegado.

Papéis e objetivos ficam ocultos durante a investigação; a identidade do lobisomem é revelada ao encerrar a partida. Conversar exige dia ativo e NPC vivo, livre, no mesmo local e ao alcance; o servidor fixa o interlocutor como jogador. O admin possui autenticação no backend; a área de jogo ainda é um protótipo local sem contas de jogadores. Veja [contratos visuais](docs/contratos_visual.md) e [mundo](docs/mundo.md).

## Verificação

```sh
uv run pytest
```

Para executar a mesma suíte contra um Redis real e isolado:

```sh
docker compose -p ml-test-suits -f compose.test.yaml up -d --wait
uv run pytest --redis-url redis://127.0.0.1:16379/0
docker compose -p ml-test-suits -f compose.test.yaml down
```

Consulte [a suíte de testes](docs/testes.md) para cobertura, isolamento e resultados.

Frontend: em `frontend/`, execute `npm test` e `npm run build`. Com o Redis isolado acima em execução, `npm run test:e2e` usa o **Brave instalado** em `/usr/bin/brave-browser` (ou `BRAVE_PATH`), sem baixar Chromium. O fluxo usa servidor e inferência de teste separados.

## Controles e autenticação

No jogo: **A/D ou setas** para andar, **E** para abordar, **M** para abrir o mapa e **Esc** para fechar janelas. O diálogo exibe o retrato e o histórico. Atualizar o navegador permite continuar o mesmo caso; iniciar outra investigação é uma ação explícita.

Cada dia jogável dura cinco minutos reais. A noite dura oito segundos e bloqueia ações; pela manhã, Floriano retorna à banca **O Clarim do Rio** na Praça Verde. O relógio continua durante ausência e as noites vencidas são resolvidas ao retomar. **E** também procura vestígios perto de uma cena. O caderno guarda objetos e depoimentos; durante conversas, use o seletor de vestígios para apresentá-los. O delegado decide com corroboração registrada; a vitória exige confirmar a transformação do preso na noite seguinte. Se todos os civis morrerem, há derrota.

NPCs podem procurar outros personagens, conversar e comentar o que Floriano lhes contou. O caderno inclui relatos ouvidos pelo jogador; o admin mostra também encontros privados, relações e a cadeia de transmissão. Abordar um NPC interrompe sua conversa atual. Até quatro encontros acontecem por dia, nos períodos de60/120/180/240 segundos; NPCs em trânsito ficam temporariamente indisponíveis. `SOCIAL_ENABLED=false` suspende novas inferências sociais e libera encontros em andamento, preservando a memória já registrada. O intervalo do worker é configurado por `SOCIAL_POLL_SECONDS` (padrão1 segundo).

O admin usa senha com hash scrypt, sessão Redis, cookie HTTPOnly/SameSite Strict, expiração, logout e limite de tentativas. Não há credencial padrão embutida; sem senha configurada, o login fica desabilitado. Detalhes em [autenticação/admin](docs/admin.md).

O antigo smoke test foi substituído pelo fluxo do jogo. A API usa bearer explícito ou gera token temporário pelo perfil AWS. Cada mensagem real ao modelo consome a cota/créditos ou gera cobrança conforme a conta. Consulte o [guia de execução](docs/execucao_docker.md) para renovar a sessão e retomar o serviço.

Se o diálogo retornar503 com o restante do jogo funcionando, consulte o [diagnóstico de indisponibilidade de diálogo](docs/bugfix_indisponibilidade_dialogo.md). O [guia de execução](docs/execucao_docker.md#diagnostico) diferencia falha de Redis, API e credencial Bedrock.

## Convenção de branches

| Branch | Finalidade |
| --- | --- |
| `feat/feature_nova` | Desenvolvimento de funcionalidades e services. |
| `fix/descricao_correcao` | Correções maiores de código. |
| `AED/aed_objetivo` | Explorações e experimentos com um objetivo definido. |
| `develop` | Integração e staging; acompanha a base de `main` e recebe alterações aprovadas antes da promoção para produção. |
| `main` | Futura branch de produção. |

As branches de trabalho partem de `develop`. Após aprovação, as alterações são integradas em `develop`; depois de validadas em staging e aprovadas para produção, seguem de `develop` para `main`.

```text
feat/feature_nova ────┐
fix/descricao_correcao ├── aprovação → develop (staging) → aprovação → main (produção)
AED/aed_objetivo ─────┘
```

Explorações em `AED/` só seguem para `develop` quando suas alterações forem aprovadas para integração.

## Estrutura

```text
src/
  __init__.py              # Pacote Python src; imports src.*
  contracts/               # Modelos internos e portas compartilhadas
  modules/                 # Characters, games, agents, conversations, world e admin
  infrastructure/          # Redis, cliente Mantle e ChatModel/output parser nativo
  prompts/                 # Tarefas e projeção das personas
  simulation/              # Agente Floriano e partidas reais via API pública
  composition.py           # Construção e injeção dos serviços
  settings.py              # Configuração por ambiente
  main.py                  # Aplicação FastAPI: src.main:app
tests/                     # Testes da API
frontend/                  # Jogo, painel, assets reais e testes Brave
deploy/                    # Gateways e startup local AWS
scripts/                   # Configuração local sem imprimir segredos
pyproject.toml             # Projeto e dependências
uv.lock                    # Versões resolvidas
Dockerfile                 # Imagem da aplicação
Makefile                   # Comandos de configuração e ciclo de vida local
compose.yaml               # API e Redis com volume persistente
```


