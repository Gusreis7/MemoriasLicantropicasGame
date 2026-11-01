# Memórias Licantropicas

Um jogo web de investigação e dedução social: entre relatos, suspeitas e interesses ocultos, descubra quem é o lobisomem. Inspirado no party game Lobisomem, com estética literária inspirada em Machado de Assis: ironia, narradores pouco confiáveis e observação das relações sociais.

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
- Jogo acessível pelo navegador. A tecnologia da interface ainda está em aberto.

A base contém catálogo de personagens, criação/consulta de partidas com sorteio secreto, Redis e conversas jogador–persona pela API, usando o harness Mantle. Ainda não há interface de jogo, encontros automáticos, crimes ou resolução de turnos.

A suíte automatizada usa Redis em memória e Redis real em Docker, com inferência simulada. O usuário confirmou o acesso real ao Qwen pelo teste local anterior; a nova mecânica não dispara chamadas AWS durante os testes automatizados.

## Planejamento

O [planejamento do projeto](docs/planejamento.md) descreve o ciclo do jogo, os módulos, o harness de agentes, a memória, as etapas de desenvolvimento e as decisões ainda em aberto.

Os [contratos entre as frentes](docs/contratos_agentes.md) fixam as interfaces e responsabilidades. A [integração da base](docs/base_agentes.md) descreve configuração, uso e limites atuais.

## Executar com Docker

Pré-requisitos: Docker com o plugin Compose e o serviço Docker em execução.

```sh
cp .env.example .env
docker compose up --build
```

O Compose prepara API e Redis com volume persistente e AOF. Os serviços são publicados apenas em localhost. A chave Bedrock pode permanecer vazia para usar o catálogo e o sorteio. `docker compose down` preserva o volume; não use `down -v` se quiser manter as partidas.

- API: http://localhost:8000/
- Documentação interativa: http://localhost:8000/docs
- Saúde: http://localhost:8000/health

Para encerrar: `Ctrl+C` e `docker compose down`.

## Desenvolvimento local

Instale o [uv](https://docs.astral.sh/uv/getting-started/installation/) e execute:

```sh
uv sync --locked
cp .env.example .env
docker compose up -d redis
uv run uvicorn memorias_licantropicas.main:app --reload
```

O uv usa a versão de Python indicada em `.python-version`. Para adicionar dependências, use `uv add pacote` ou `uv add --dev pacote` e versione também o `uv.lock` atualizado.

## API inicial

- `GET /api/v1/characters`: apresentações públicas dos sete suspeitos.
- `GET /api/v1/characters/{character_id}`: apresentação de um suspeito.
- `POST /api/v1/games`: cria partida e sorteia um lobisomem; corpo opcional `{}`.
- `GET /api/v1/games/{game_id}`: estado público da partida.
- `POST /api/v1/games/{game_id}/conversations`: abre conversa com `{"npc_id": "capitu"}`.
- `GET /api/v1/games/{game_id}/conversations/{conversation_id}`: consulta a conversa.
- `POST /api/v1/games/{game_id}/conversations/{conversation_id}/messages`: envia `{"content": "O que sabe sobre Brás Cubas?"}` e recebe a fala da persona.
- `GET /api/v1/games/{game_id}/conversations/{conversation_id}/messages`: recupera o histórico.

Papéis e objetivos privados não aparecem nos schemas públicos. O servidor fixa o interlocutor como jogador; não aceita IDs de remetente no corpo. A API ainda não possui autenticação ou propriedade de partidas; esta base é para desenvolvimento local. Veja [conversa jogador–persona](docs/conversa_jogador_persona.md) para configuração e exemplos.

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

## Conversar com uma persona

Com o perfil `terraform` autenticado na AWS CLI, inicie Redis e a API no host:

```sh
uv sync --locked
docker compose up -d redis
AWS_PROFILE=terraform AWS_REGION=us-east-1 uv run uvicorn memorias_licantropicas.main:app --reload
```

Em http://localhost:8000/docs, crie uma partida, abra uma conversa com o ID da partida e um NPC, e envie mensagens usando o ID da conversa retornado. Crie uma partida nova para usar o catálogo versão 2.

O antigo `smoketest.py` foi removido. A API gera tokens temporários em memória quando `AWS_PROFILE` está configurado e não há bearer token explícito. As dependências `aws-bedrock-token-generator` e `botocore[crt]` agora fazem parte do runtime. No Docker da API, o cache de login do host não é montado automaticamente; use o bearer token configurado ou execute a API no host para usar o perfil. Cada mensagem enviada ao modelo consome a cota/créditos ou gera cobrança conforme a conta.

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
src/memorias_licantropicas/
  contracts/               # Modelos internos e portas compartilhadas
  modules/                 # Characters, games, agents e conversations
  infrastructure/          # Redis e cliente Mantle
  composition.py           # Construção e injeção dos serviços
  settings.py              # Configuração por ambiente
  main.py                  # Aplicação FastAPI
tests/                     # Testes da API
pyproject.toml             # Projeto e dependências
uv.lock                    # Versões resolvidas
Dockerfile                 # Imagem da aplicação
compose.yaml               # API e Redis com volume persistente
```


