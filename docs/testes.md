# Testes e simulações

A suíte comum usa clientes de modelo controlados e não exige saldo AWS. Os testes de API exercitam a aplicação por ASGI; os testes Redis usam fakeredis por padrão. Isso verifica as regras e a integração, mas não mede sozinho o comportamento de um modelo real.

## Backend

```sh
uv sync --locked
uv run pytest -q
```

A cobertura inclui sorteio e sigilo de papéis, reserva de ações, persistência e conflitos, mesa e confirmação recíproca de álibis, isolamento de conhecimento, proveniência social, admissão de relatos, autenticação administrativa e falhas de inferência. Os cenários atuais estão em `tests/`; não se fixa aqui uma contagem de testes que envelheceria a cada mudança.

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
npm run test:e2e
```

O E2E usa Brave em `/usr/bin/brave-browser`; ajuste `BRAVE_PATH` se necessário. Confira a configuração Playwright para portas e inicialização do servidor. O build verifica TypeScript e gera os recursos servidos pelas imagens.

## Infraestrutura e entrega

```sh
python3 -m unittest discover -s tests/deployment -p 'test_*.py'
terraform fmt -check -recursive infra/terraform
```

Nas raízes Terraform, execute `terraform init -backend=false`, `terraform validate` e `terraform test` conforme a configuração local. Os testes de Terraform usam providers simulados; não aplicam recursos na AWS. Os testes de entrega verificam políticas, manifesto, instalador e isolamento dos containers. A arquitetura e a reprodução em uma conta real estão em [solução AWS](solucao_aws.md) e [reprodução na AWS](reproducao_aws.md).

## Smoke pela API real

Inicie a aplicação e configure as credenciais do modelo conforme o [guia local](deploy_local.md). Na raiz:

```sh
uv run python scripts/smoke_table_api.py --api-url http://127.0.0.1:7079 --games 2 --output artifacts/simulations/table-live.json
```

Esse script cria partidas reais e verifica invariantes da mesa pela API. Ele usa as credenciais administrativas configuradas para observar o estado; consulte `--help` para opções. O ambiente recebe partidas e chamadas reais, portanto use uma instalação de avaliação.

## Floriano controlado por LLM

```sh
uv run python scripts/run_session_simulations.py --api-url http://127.0.0.1:7079 --games 10 --max-live-calls 200
```

O agente decide ações e interage com a API do jogo. As sessões e os relatórios salvam resultados, ações, interrupções e uso; veja `--help` para controlar saída e limites. Não há provedor offline nesse loop.

`--max-live-calls` limita somente as chamadas do agente Floriano. As inferências de NPCs, mestre e convivência feitas no servidor são adicionais. Uma simulação interrompida não conta como vitória ou derrota concluída. Antes de aumentar N, confira uma execução curta e seus relatórios.

Os arquivos datados em `docs/reports/` são evidências históricas, com seus próprios cenários e versões. Eles não substituem executar os testes no checkout atual.
