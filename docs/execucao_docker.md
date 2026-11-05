# Executar o jogo com Docker

Este é o guia operacional atual. Os demais documentos registram etapas de desenvolvimento e podem conter comandos históricos.

## Início rápido

É necessário ter Make e Docker com o plugin Compose em execução. Para diálogos com os NPCs, configure um perfil AWS com acesso ao Bedrock Mantle **ou** preencha `AWS_BEARER_TOKEN_BEDROCK` no `.env`. Sem credencial válida, o jogo pode abrir, mas as respostas do modelo falham.

Na raiz do projeto:

```sh
make setup
```

Esse comando cria ou atualiza o `.env` local sem sobrescrever os valores existentes, gera uma senha admin se necessário, seleciona o perfil AWS configurado ou o bearer explícito, constrói as imagens, sobe os serviços e aguarda a saúde de Redis e API. A primeira execução baixa e constrói imagens e leva mais tempo.

Se o Docker do host exigir `sudo`, os mesmos alvos podem ser executados como `sudo make setup` e `sudo make up`. O launcher identifica `SUDO_USER`, usa o diretório `.aws` desse usuário em vez de `/root/.aws` e mantém o `.env` pertencendo ao usuário original.

## Comandos do ambiente

| Comando | Efeito |
| --- | --- |
| `make setup` | Prepara, constrói e inicia toda a aplicação; use na primeira execução ou após mudar o código. |
| `make up` | Inicia rapidamente com as imagens já construídas. |
| `make down` | Remove containers e rede, preservando o volume Redis e as partidas. |
| `make destroy` | Remove containers, rede e o volume Redis; apaga permanentemente todas as partidas. |
| `make status` | Mostra o estado dos serviços. |
| `make logs` | Acompanha os logs de todos os serviços. |

`make destroy` é a limpeza completa solicitada para recomeçar sem dados. Depois dele, execute `make setup` para criar um ambiente vazio. Os scripts em `scripts/` são usados pelo Makefile e continuam disponíveis para diagnóstico direto.

| Endereço | Serviço |
| --- | --- |
| http://localhost:7077 | Jogo |
| http://localhost:7078 | Painel admin |
| http://localhost:7079/docs | API |

As credenciais do painel estão nos campos `ADMIN_USERNAME` e `ADMIN_PASSWORD` do `.env` local. Esse arquivo não é versionado; não compartilhe seu conteúdo. Os dados do jogo ficam no volume `redis_data`. Partidas da versão 2 do catálogo continuam legíveis após a atualização para a versão 3, sem reinicializar o Redis. Use `make down` no encerramento comum; `make destroy` é reservado para quando você realmente quiser apagar as partidas.

## Credencial Bedrock

O caminho comum usa o perfil configurado em `AWS_PROFILE` no `.env` (`terraform` no exemplo). Autentique o perfil com a AWS CLI no host antes de iniciar. O overlay `compose.aws-local.yaml` monta a pasta AWS do host somente para leitura e copia a sessão para um filesystem temporário privado do container. Credenciais não entram na imagem nem no volume do Redis. Quando a cópia expira, a API atualiza o cache a partir desse volume e repete a geração do token uma vez; depois de `aws login`, basta enviar a mensagem novamente. `make up` continua disponível como recuperação manual e recria apenas a API.

Quem usa um bearer Bedrock explícito pode preencher `AWS_BEARER_TOKEN_BEDROCK` no `.env`. O script escolhe o Compose básico nesse caso. O navegador nunca recebe essa credencial. A rota `/health` verifica a API, mas não testa uma inferência Bedrock; se a conversa retornar 503, consulte [o diagnóstico específico](bugfix_indisponibilidade_dialogo.md).

## Diagnóstico

Consulte o estado e os logs na raiz do projeto:

```sh
docker compose ps --all
docker compose logs --tail=100 redis api
```

Se Redis aparece como `Exited` ou `unhealthy`, a API fica pendente porque o Compose aguarda Redis saudável. Primeiro leia **as linhas de erro do Redis**. Um aviso `vm.overcommit_memory is set to 0` pode aparecer nos logs; ele é uma recomendação de ajuste do host e, sozinho, não explica a falha de inicialização. O incidente observado aqui foi a leitura inválida de `appendonly.aof.14.incr.aof`, um arquivo AOF incremental. Nesse caso, reiniciar o container sem tratar o AOF repete o erro.

Se o log indicar AOF corrompido, consulte as instruções do reparo sem alterar dados:

```sh
./scripts/repair_redis_aof.sh
```

Depois de confirmar a falha no log, pare os serviços e solicite o reparo:

```sh
docker compose stop
./scripts/repair_redis_aof.sh --repair
make up
```

O reparo faz um backup de **todo o volume** em `artifacts/redis-backups/` antes de modificar qualquer arquivo, valida o arquivo de backup, aplica `redis-check-aof --fix` e testa a subida do Redis. O comando mostra o caminho exato do backup. O reparo pode descartar registros após o primeiro trecho corrompido; confira a contagem de chaves e as partidas após subir. Não apague o volume para contornar esse erro.

No incidente de 04/11/2026, o backup original foi preservado em `artifacts/redis-backups/20261104-initial-recovery/`. O reparo descartou 17.445.104 bytes da cauda corrompida do AOF incremental; gravações recentes nessa parte podem ter sido perdidas. O Redis voltou a carregar 614 chaves. Não há como afirmar que todo o histórico recente foi recuperado apenas pela contagem de chaves.

Se Redis estiver saudável mas a API não subir, consulte `docker compose logs --tail=100 api`. Se ambos estiverem saudáveis e só o diálogo falhar, verifique a credencial Bedrock e o [fluxo de recuperação de resposta](bugfix_indisponibilidade_dialogo.md). Para uma inspeção manual do Redis, inclua o override `compose.debug.yaml`, que publica a porta `127.0.0.1:7080` apenas no host; a subida normal mantém o Redis privado na rede Docker.

## Desenvolvimento fora do Docker

Para rodar a API no host, instale [uv](https://docs.astral.sh/uv/getting-started/installation/) e use o Redis do Compose com o override de depuração:

```sh
uv sync --locked
python3 scripts/configure_local.py
docker compose -f compose.yaml -f compose.debug.yaml up -d --wait redis
REDIS_URL=redis://127.0.0.1:7080/0 AWS_PROFILE=terraform uv run uvicorn src.main:app --port 7079 --reload
```

Em outro terminal, dentro de `frontend/`, execute `npm ci` e `npm run dev`; o Vite usa a porta 7081. O admin no Vite precisa dessa origem em `ADMIN_ALLOWED_ORIGINS`. O Docker normal já usa as origens locais do painel. O Redis de testes (`compose.test.yaml`, porta 16379) é separado e não compartilha o volume do jogo; a [suíte de testes](testes.md) documenta esse fluxo.
