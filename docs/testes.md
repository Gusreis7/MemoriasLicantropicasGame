# Testes da aplicação

A suíte padrão verifica a API, a proteção HTTP e a configuração de produção. Ela usa armazenamento isolado e não chama os modelos de IA. Os testes de navegador e as avaliações de partidas são executados separadamente.

## Backend

```sh
uv sync --locked
uv run pytest -q
```

Esse comando executa `test_api.py`, `test_api_security.py` e `test_deployment_security.py`. Para investigar uma mudança específica, você pode selecionar os arquivos relacionados. Por exemplo, os testes dos KPIs verificam os resultados das partidas, a autenticação, a contagem de sessões e a leitura sem alterar o jogo:

```sh
uv run pytest -q tests/test_admin.py tests/test_telemetry.py
```

Para repetir a suíte com Redis real e descartável:

```sh
docker compose -p ml-test-suits -f compose.test.yaml up -d --wait
uv run pytest -q --redis-url redis://127.0.0.1:16379/0
docker compose -p ml-test-suits -f compose.test.yaml down
```

Os testes usam prefixos exclusivos e removem somente suas chaves. Não aponte essa execução para produção. Esse Compose não testa recuperação AOF ou persistência em disco.

## Frontend

Na pasta `frontend`:

```sh
npm ci
npm test
npm run build
```

O build verifica o TypeScript e prepara os arquivos que serão servidos pelo Nginx, incluindo as imagens WebP sem perda. As conversões existentes são reaproveitadas.

Para testar no navegador, inicie o Redis descartável a partir da raiz do projeto e depois execute o Playwright:

```sh
docker compose -p ml-test-suits -f compose.test.yaml up -d --wait
cd frontend
npm run test:e2e -- admin-kpis.spec.ts
```

O exemplo testa o painel com a API real e um modelo substituto de teste. Ele confere os seis indicadores e a proteção dos endpoints. Para percorrer as demais verificações de interface, use `npm run test:e2e` sem selecionar um arquivo. O Playwright inicia seus próprios servidores e usa Brave em `/usr/bin/brave-browser`; ajuste `BRAVE_PATH` se o navegador estiver em outro caminho.

Ao terminar, volte à raiz e encerre o Redis de testes:

```sh
cd ..
docker compose -p ml-test-suits -f compose.test.yaml down
```

## Infraestrutura e entrega

```sh
python3 -m unittest discover -s tests/deployment -p 'test_*.py'
terraform fmt -check -recursive infra/terraform
```

Nas raízes Terraform, execute `terraform init -backend=false`, `terraform validate` e `terraform test` conforme a configuração local. Os testes de Terraform usam providers simulados; não aplicam recursos na AWS. Os testes de entrega verificam políticas, manifesto, instalador e isolamento dos containers. A arquitetura e a reprodução em uma conta real estão em [solução AWS](solucao_aws.md) e [reprodução na AWS](reproducao_aws.md).

## Check do delivery

O Actions constrói a imagem e executa `scripts/smoke_application.py` como o usuário não privilegiado da aplicação, sem rede externa e com filesystem somente leitura. São três verificações:

1. Sintaxe Python usando `compile()` em memória, sem criar `__pycache__`.
2. Inicialização, `/health` e catálogo público.
3. Admin sem autenticação rejeitado e documentação de produção desativada.

Não usa Redis externo, LLM, navegador ou simulação de partidas. A entrega continua verificando saúde interna via instalador e DNS/HTTPS depois da instalação.

## Avaliação manual de partidas

Os scripts `scripts/smoke_table_api.py` e `scripts/run_session_simulations.py` continuam disponíveis para investigar o comportamento do jogo pela API. Consulte as opções antes de executá-los:

```sh
uv run python scripts/smoke_table_api.py --help
uv run python scripts/run_session_simulations.py --help
```

O simulador pode usar o modelo real para interpretar Floriano e gerar custos. Use um ambiente de avaliação separado, com seu próprio namespace Redis. Essas avaliações são opcionais e não fazem parte das verificações do Actions.
