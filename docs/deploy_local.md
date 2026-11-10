# Reprodução local

É possível rodar o jogo, a API, o Redis e o painel administrativo na sua
máquina. O que **não** roda localmente nesta versão é o modelo de linguagem:
as conversas utilizam **Qwen3-32B** pelo **Amazon Bedrock Mantle**.

Desenvolvi e testei o projeto usando créditos da AWS. Esses créditos não são
fornecidos com o código. Para jogar com os NPCs, você precisa de uma identidade
AWS com acesso ao Bedrock e ao modelo configurado. As chamadas podem gerar custo.
**Não há integração pronta com Ollama, LM Studio ou outro servidor de LLM local.**

## 1. Preparar a aplicação

Instale Git, Python 3, Make, Docker e Docker Compose. Clone o repositório e
execute, na raiz:

```sh
git clone https://github.com/Gusreis7/MemoriasLicantropicasGame.git
cd MemoriasLicantropicasGame
make setup
make status
curl --fail http://127.0.0.1:7079/health
```

O `make setup` prepara o `.env`, gera uma senha administrativa se ainda não
existir e inicia os serviços. Ele preserva as configurações anteriores.
O `/health` confirma API e Redis; **não** testa a conexão com o Bedrock.

| Serviço | Endereço padrão |
| --- | --- |
| Jogo | http://127.0.0.1:7077 |
| Painel administrativo | http://127.0.0.1:7078 |
| API / Swagger | http://127.0.0.1:7079/docs |

O Redis não publica uma porta no Compose de uso normal. As credenciais locais
do painel ficam em `ADMIN_USERNAME` e `ADMIN_PASSWORD` no `.env`. Não versione
esses valores.

## 2. Configurar o Bedrock

O modelo padrão é `qwen.qwen3-32b`, usando o endpoint Bedrock Mantle na região
`us-east-1`. Escolha **uma** das formas de autenticação no `.env`:

**Perfil AWS:**

```dotenv
AWS_REGION=us-east-1
AWS_PROFILE=seu-perfil
```

O perfil deve estar configurado no AWS CLI e autorizado a chamar o modelo.
Caso use SSO, autentique-se antes de subir a aplicação:

```sh
aws sso login --profile seu-perfil
make up
```

O launcher monta as configurações AWS somente para a API. Para perfis guardados
fora de `~/.aws`, consulte a opção `AWS_CONFIG_DIR` usada pelo launcher.

**Token Bedrock:**

```dotenv
AWS_REGION=us-east-1
AWS_PROFILE=
AWS_BEARER_TOKEN_BEDROCK=seu-token
```

Salve o `.env` e execute `make up`. O token é um segredo; não o publique nem o
adicione ao Git. Para uma instalação real, verifique também as permissões e a
disponibilidade do modelo na sua conta.

Abra o jogo e teste uma conversa com um NPC. Se ela falhar, consulte `make logs`.
O endpoint `/health` pode continuar saudável mesmo sem credenciais de IA.
A variável `BEDROCK_MODEL` seleciona o modelo do serviço configurado, mas não
ativa inferência local nem troca automaticamente de provedor.

## 3. Jogar e preservar as partidas

Abra http://127.0.0.1:7077. O tutorial aparece na primeira visita e pode ser
reaberto no cabeçalho. Use **A/D ou setas** para andar, **E** para interagir,
**Enter** para confirmar destinos e **Esc** para fechar o menu. O mapa permite
trocar de lugar. Você investiga depoimentos e objetos, confirma álibis e leva
as provas à delegacia para acusar um suspeito.

Para acompanhar ou reiniciar os serviços:

```sh
make logs
make down
make up
```

`make down` preserva o volume Redis e as partidas. `make setup` reconstrói os
serviços depois de alterações de código ou dependências. **`make destroy`
apaga o volume Redis e todas as partidas.** O formato atual também recusa
partidas antigas incompatíveis; não há migração automática.

Para trocar a senha administrativa local:

```sh
python3 scripts/configure_local.py --reset-admin-password
make up
```

Leia os novos dados no `.env`. O painel mostra visitas, jogadores ativos,
partidas iniciadas, vitórias, derrotas e partidas sem desfecho, além de
indicadores de consumo de IA. É somente de leitura, mas contém detalhes da
investigação; não o exponha publicamente. Na AWS o acesso usa túnel SSM.
As visitas são sessões do navegador que expiram após 30 minutos sem atividade;
"jogadores ativos" considera presença nos últimos 90 segundos. Os totais podem
levar até 15 segundos para atualizar.

## 4. Desenvolver sem os containers da aplicação

Para trabalhar diretamente no código, use Python 3.13, `uv` e Node.js 22.12 ou
superior. Deixe o Redis em um container separado e rode a API no host. Pare a
API do Compose se ela já estiver usando a porta `7079`.

```sh
uv sync --locked
python3 scripts/configure_local.py
docker compose -f compose.yaml -f compose.debug.yaml up -d --wait redis
REDIS_URL=redis://127.0.0.1:7080/0 AWS_PROFILE=seu-perfil uv run uvicorn src.main:app --host 127.0.0.1 --port 7079 --reload --no-proxy-headers
```

Em outro terminal:

```sh
cd frontend
npm ci
npm run dev
```

Se estiver usando autenticação por token, omita `AWS_PROFILE=seu-perfil` do
comando da API e configure `AWS_BEARER_TOKEN_BEDROCK` no `.env`.

O Vite usa a porta `7081` e encaminha chamadas para a API em `7079`. Para abrir
o painel administrativo nessa origem, inclua-a em `ADMIN_ALLOWED_ORIGINS`.

Os testes não precisam de credenciais de IA; veja o [guia de testes](testes.md).
Se o Redis não subir por problema no AOF, consulte os logs e leia
`scripts/repair_redis_aof.sh` antes de tentar reparar. O script prevê backup;
não apague os dados para resolver um erro de inicialização.

## Observações de desempenho

A interface carrega os cenários conforme necessário. O build cria versões WebP
e recursos otimizados em `frontend/public/assets/optimized/`; os originais
continuam no projeto. Para investigar lentidão em uma conversa, compare o tempo
da requisição no navegador com o cabeçalho `Server-Timing` da API.

Os contadores de visitas usam sessões do navegador, sem armazenar IPs nas
métricas. Os dados do painel permanecem enquanto o Redis for preservado.
