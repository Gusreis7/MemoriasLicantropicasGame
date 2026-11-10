# Testes

Os testes comuns usam dados isolados e modelos controlados. Eles não chamam
a AWS e não precisam de créditos ou credenciais do Bedrock. Passar nessa suíte
não confirma que os NPCs conseguirão conversar com o modelo real.

A suíte cobre API, segurança, dados, mesa determinística, movimento e entrega.
Procurei manter testes de contratos e falhas concretas, evitando repetir uma
partida inteira para cada personagem.

## Backend

Na raiz do projeto:

```sh
uv sync --locked
uv run pytest -q
```

Esse comando roda a checagem curta: API, proteção HTTP e configuração de produção.
Para verificar todo o backend:

```sh
uv run pytest -q tests
```

Você também pode escolher a parte que mudou:

| Área | Arquivos |
| --- | --- |
| Conversas e mesa | `test_table_api.py`, `test_table_delivery.py`, `test_table_exhaustion.py` |
| Saída estruturada | `test_native_tool_output.py`, `test_structured_generation.py` |
| Painel e visitas | `test_admin.py`, `test_telemetry.py` |
| Movimento | `test_world.py` |

Por exemplo:

```sh
uv run pytest -q tests/test_table_api.py tests/test_table_delivery.py tests/test_table_exhaustion.py
```

Os testes da mesa verificam confirmação de álibis, permissões, repetição de
assuntos e gravação das falas. Também conferem ações durante a inferência e o
descarte de uma resposta quando o dia, a distância ou os fatos mudam.

Para repetir com Redis real descartável:

```sh
docker compose -p ml-test-suits -f compose.test.yaml up -d --wait
uv run pytest -q tests/test_table_api.py --redis-url redis://127.0.0.1:16379/0
docker compose -p ml-test-suits -f compose.test.yaml down
```

Cada teste remove somente suas próprias chaves. Use esse Redis separado, nunca
o banco de uma instalação em uso. Esses testes não verificam recuperação AOF.

## Interface

Na pasta `frontend`:

```sh
npm ci
npm test
npm run build
```

Para testes no navegador, inicie antes o Redis descartável pelo comando acima.
O Playwright espera Brave por padrão. Se necessário, defina `BRAVE_PATH` com o
caminho do navegador instalado na sua máquina. Depois, em `frontend`:

```sh
npm run test:e2e -- admin-kpis.spec.ts
```

Sem selecionar um arquivo, o comando executa os demais testes de navegador.
Ao terminar, encerre o Compose de testes.

## Infraestrutura e entrega

```sh
python3 -m unittest discover -s tests/deployment -p 'test_*.py'
terraform fmt -check -recursive infra/terraform
```

Nas raízes Terraform, `terraform validate` e `terraform test` conferem a
configuração após o init. Os testes usam providers simulados e não criam recursos
na AWS. Em forks, adapte primeiro as restrições descritas no [guia de publicação](reproducao_aws.md).

O Actions faz um smoke curto da imagem: sintaxe Python, inicialização, saúde,
catálogo, autenticação do admin e documentação pública desativada. Essa etapa
não simula partidas. Depois da instalação, a entrega verifica saúde e HTTPS.

## Avaliação opcional com o modelo real

A versão atual utiliza **Qwen3-32B pelo Amazon Bedrock Mantle**, sem opção pronta
de LLM local. Para verificar qualidade, latência e consumo durante uma partida,
use uma conta AWS com acesso ao modelo. Desenvolvi o projeto com créditos da AWS,
mas essas simulações podem gerar cobranças para quem as reproduzir.

Os scripts abaixo ajudam a investigar o comportamento do jogo pela API, fora
dos testes comuns:

```sh
uv run python scripts/smoke_table_api.py --help
uv run python scripts/run_session_simulations.py --help
```

Use um ambiente de avaliação separado. O simulador pode chamar o modelo real,
gerar custos e salvar estatísticas. Ele não faz parte das verificações do Actions.

## Arquivos gerados

`artifacts/` fica fora do Git e recebe capturas, relatórios e resultados de
avaliações. Esses arquivos não são necessários para executar o jogo e podem ser
apagados quando não forem mais úteis. Os scripts recriam suas pastas de saída.
Se apagar um plano de infraestrutura, execute a etapa `plan` novamente antes de `apply`.

Confira o conteúdo antes de apagar tudo: `aws-bootstrap/` pode conter backups do
state Terraform e a configuração usada para provisionar, e `redis-backups/` pode
conter cópias de recuperação. Preserve esses dados enquanto forem necessários
para operar ou recuperar sua instalação.
