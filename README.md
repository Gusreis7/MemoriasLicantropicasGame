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

Por enquanto, a base contém apenas uma API executável e uma verificação de saúde. Não há partidas, agentes, banco de dados ou interface de jogo implementados.

## Planejamento

O [planejamento do projeto](docs/planejamento.md) descreve o ciclo do jogo, os módulos, o harness de agentes, a memória, as etapas de desenvolvimento e as decisões ainda em aberto.

## Executar com Docker

Pré-requisitos: Docker com o plugin Compose e o serviço Docker em execução.

```sh
docker compose up --build
```

- API: http://localhost:8000/
- Documentação interativa: http://localhost:8000/docs
- Saúde: http://localhost:8000/health

Para encerrar: `Ctrl+C` e `docker compose down`.

## Desenvolvimento local

Instale o [uv](https://docs.astral.sh/uv/getting-started/installation/) e execute:

```sh
uv sync --locked
uv run uvicorn memorias_licantropicas.main:app --reload
```

O uv usa a versão de Python indicada em `.python-version`. Para adicionar dependências, use `uv add pacote` ou `uv add --dev pacote` e versione também o `uv.lock` atualizado.

## Verificação

```sh
uv run pytest
```

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
src/memorias_licantropicas/  # API e código Python
tests/                     # Testes da API
pyproject.toml             # Projeto e dependências
uv.lock                    # Versões resolvidas
Dockerfile                 # Imagem da aplicação
compose.yaml               # Execução local em container
```


