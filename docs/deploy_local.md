# Deploy local

## Requisitos e primeira execução

Use Git, Python 3, Make, Docker Engine e Docker Compose. Para desenvolvimento fora dos containers, use também `uv`, Python 3.13 e Node.js 22.12 ou superior.

Na raiz do checkout:

```sh
make setup
make status
curl --fail http://127.0.0.1:7079/health
```

O comando prepara o `.env` e gera uma senha administrativa se você ainda não tiver uma. Depois, constrói as imagens e inicia os serviços. Suas configurações existentes são preservadas. Quando terminar, abra:

| Serviço | Endereço |
| --- | --- |
| Jogo | http://127.0.0.1:7077 |
| Administração | http://127.0.0.1:7078 |
| API e documentação local | http://127.0.0.1:7079/docs |

O usuário e a senha do admin ficam em `ADMIN_USERNAME` e `ADMIN_PASSWORD` no `.env`. Não publique esse arquivo. O Redis não expõe porta no Compose normal.

## Recursos e desempenho

Ao construir a interface ou iniciar o Vite, o Sharp gera cópias WebP sem perda dos PNGs. As dimensões, a transparência e as coordenadas usadas pelas animações são mantidas. Os originais continuam no projeto, e as cópias menores ficam em `frontend/public/assets/optimized/`, fora do Git. O processo reaproveita conversões existentes e salva um resumo dos tamanhos em `report.json` nessa pasta.

O nome de cada imagem otimizada depende do seu conteúdo. Assim, o navegador pode guardá-la por um ano e buscar outro arquivo quando a arte mudar. O mesmo vale para os scripts e estilos versionados. HTML, manifestos e imagens sem versão são revalidados; CSS, JavaScript e JSON também usam gzip. Essas configurações fazem parte da imagem web e chegam à AWS pelo deploy normal.

A cena carrega inicialmente as três iluminações do local atual. Os outros locais são carregados na primeira visita e reutilizados depois. Durante essa primeira carga, o indicador bloqueia a caminhada até os recursos estarem disponíveis. Recarregue a página após atualizar a aplicação para receber o novo código.

## KPIs do administrador

Os números no topo do painel consideram todas as partidas armazenadas, mesmo aquelas que não aparecem na página atual da lista. Você pode acompanhar quantas começaram, quantas terminaram em vitória ou derrota e quantas seguem sem desfecho. “Sem desfecho” inclui partidas em andamento e partidas interrompidas. Abrir o painel não avança fases nem executa ações no jogo. Os totais podem levar até 15 segundos para refletir uma mudança.

Uma conexão representa uma sessão de visita ao jogo. Recarregar a página não cria uma nova visita enquanto a sessão estiver válida, e abas do mesmo navegador compartilham o cookie. Depois de 30 minutos sem atividade, o próximo acesso conta como outra sessão. Isso não é uma contagem de pessoas únicas.

Enquanto a aba está visível, o jogo informa sua presença a cada 30 segundos. O cartão de ativos considera as sessões que enviaram essa informação nos últimos 90 segundos. O cookie é HttpOnly, e o Redis guarda apenas um hash do identificador, contadores e horários. As métricas não armazenam IPs, e o endpoint de presença fica fora do registro de acessos do Nginx.

A contagem de visitas começa no primeiro acesso após instalar essa funcionalidade. Acessos anteriores não são estimados. Os números sobrevivem aos reinícios enquanto o volume Redis for preservado.

Para consultar os indicadores pela API, use `GET /admin/api/v1/metrics` com uma sessão administrativa. A resposta não pode ser armazenada em cache e o endpoint não aceita escrita. A presença enviada pelo jogo usa `POST /api/v1/visits`, sem expor métricas públicas ou alterar partidas.

## Trocar a senha do painel

Para gerar outra senha local, execute na raiz do projeto:

```sh
python3 scripts/configure_local.py --reset-admin-password
make up
```

Consulte `ADMIN_PASSWORD` no `.env` e entre novamente no painel. Essa troca não altera a senha da AWS nem apaga partidas. Para trocar a senha de produção, siga o [guia da AWS](reproducao_aws.md#5-admin-e-preservação).

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
