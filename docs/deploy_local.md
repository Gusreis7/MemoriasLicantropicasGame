# Deploy local

## Requisitos e primeira execução

Use Git, Python 3, Make, Docker Engine e Docker Compose. Para desenvolvimento fora dos containers, use também `uv`, Python 3.13 e Node.js 22.12 ou superior.

Na raiz do checkout:

```sh
make setup
make status
curl --fail http://127.0.0.1:7079/health
```

O launcher cria ou completa `.env`, gera uma senha administrativa quando ausente, ajusta suas permissões e constrói as imagens. Valores já definidos são preservados. Abra:

| Serviço | Endereço |
| --- | --- |
| Jogo | http://127.0.0.1:7077 |
| Administração | http://127.0.0.1:7078 |
| API e documentação local | http://127.0.0.1:7079/docs |

O usuário e a senha do admin ficam em `ADMIN_USERNAME` e `ADMIN_PASSWORD` no `.env`. Não publique esse arquivo. O Redis não expõe porta no Compose normal.

## Credenciais do modelo

O modelo configurado por padrão é `qwen.qwen3-32b`, via Bedrock Mantle em `us-east-1`. Escolha uma das formas suportadas e confirme que sua identidade tem acesso ao serviço e ao modelo:

- Perfil AWS: configure `AWS_PROFILE` e `AWS_REGION` no `.env`. Se o perfil usa SSO, autentique no host com `aws sso login --profile NOME_DO_PERFIL` antes de iniciar. O launcher inclui `compose.aws-local.yaml`, monta a origem de credenciais em modo de leitura e prepara uma cópia privada para a API.
- Bearer explícito: preencha `AWS_BEARER_TOKEN_BEDROCK` no `.env` e deixe `AWS_PROFILE` vazio.

Depois de alterar configuração, execute `make up`; se alterar código ou dependências, use `make setup`. Nunca coloque credenciais no Git. O endpoint `/health` verifica a aplicação e o Redis, não comprova uma inferência bem-sucedida. Os diálogos canônicos têm fallback de tom, mas outras tarefas narrativas podem precisar do modelo.

## Operação e dados

```sh
make logs
make down
make up
```

`make down` preserva o volume e as partidas. `make destroy` apaga definitivamente o volume Redis e todas as partidas; use somente quando quiser reiniciar os dados. O formato atual de investigação é 2 e recusa partidas antigas incompatíveis. Não há migração de dados legados.

Se o Redis não iniciar, consulte os logs antes de remover dados. `scripts/repair_redis_aof.sh` fornece um fluxo específico de diagnóstico e reparo com backup em `artifacts/redis-backups`; leia o script antes de usar `--repair` e pare os serviços conforme suas instruções. Esses backups não são resíduos descartáveis de build.

## Desenvolvimento sem container da API

Instale as dependências e exponha somente o Redis de desenvolvimento. Se a API do Compose já usa 7079, pare-a antes de executar Uvicorn.

```sh
uv sync --locked
python3 scripts/configure_local.py
docker compose -f compose.yaml -f compose.debug.yaml up -d --wait redis
REDIS_URL=redis://127.0.0.1:7080/0 AWS_PROFILE=terraform uv run uvicorn src.main:app --host 127.0.0.1 --port 7079 --reload --no-proxy-headers
```

Substitua `terraform` pelo seu perfil. Em outro terminal:

```sh
cd frontend
npm ci
npm run dev
```

O Vite serve em 7081 e encaminha a API para 7079. Para usar o admin nessa origem, inclua-a em `ADMIN_ALLOWED_ORIGINS`. As portas de jogo/admin do Compose continuam sendo as opções para executar o frontend já construído.

## Validação e diagnóstico

Execute as suítes e os smokes descritos em [testes](testes.md). Se uma porta estiver ocupada, confira `docker compose -f compose.yaml ps --all` e os processos locais. Se somente tarefas de modelo falharem, verifique o perfil/token, a região e os logs da API. Não é necessário apagar o Redis para corrigir credenciais.

Para produção, siga [reprodução na AWS](reproducao_aws.md); o Compose local não substitui a configuração de produção.
