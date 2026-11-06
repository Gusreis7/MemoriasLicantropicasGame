# Testes da aplicação

A suíte padrão está limitada a API, segurança HTTP e configuração de produção. Não executa partidas simuladas nem chamadas a modelos. Os testes de API usam transporte ASGI e armazenamento isolado.

## Backend

```sh
uv sync --locked
uv run pytest -q
```

O padrão seleciona `test_api.py`, `test_api_security.py` e `test_deployment_security.py`. Os demais testes especializados remanescentes podem ser chamados explicitamente pelo caminho; não fazem parte do deploy. Os três arquivos de testes do simulador foram removidos.

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

## Check do delivery

O Actions constrói a imagem e executa `scripts/smoke_application.py` como o usuário não privilegiado da aplicação, sem rede externa e com filesystem somente leitura. São três verificações:

1. Sintaxe Python usando `compile()` em memória, sem criar `__pycache__`.
2. Inicialização, `/health` e catálogo público.
3. Admin sem autenticação rejeitado e documentação de produção desativada.

Não usa Redis externo, LLM, navegador ou simulação de partidas. A entrega continua verificando saúde interna via instalador e DNS/HTTPS depois da instalação.

Os scripts de avaliação manual permanecem disponíveis no repositório, mas não são pré-requisitos nem checks do Actions.
