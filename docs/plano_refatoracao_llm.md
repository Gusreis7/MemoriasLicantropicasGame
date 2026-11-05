# Plano consolidado da refatoração LLM

Este plano reúne a separação inicial de responsabilidades e a correção posterior
exigida pelo usuário. **A proposta inicial de JSON por instruções foi substituída**
por ferramentas nativas, ChatModel LangChain e PydanticToolsParser. A especificação
dessa correção está em [plano_saida_nativa_llm.md](plano_saida_nativa_llm.md).

## Objetivo e frentes

Separar transporte Mantle, prompts de persona, contratos tipados, validação
semântica, grafos LangGraph e persistência. Preservar o motor determinístico,
privacidade por ator, medição de chamadas e contratos REST. Push permanece manual.

| Frente | Responsabilidade |
| --- | --- |
| `feat/llm_contracts`, seguida de `feat/native_llm_provider` | Port de ferramentas, ChatModel, saída nativa, schemas Pydantic, erros e orçamento |
| `feat/llm_graph` | Grafo de diálogo, estado por sessão, prompts de persona, validação e fallback |
| `feat/llm_simulation`, seguida de `feat/native_simulation_clients` | Partidas completas e clientes simulados que emitem envelopes nativos |
| `feat/native_text_validation` | Validações textuais explícitas, sem dependência de regex no aplicativo |
| Integração | Mestre, conhecimento/social, limpeza de consumidores, documentação e layout final `src/` |

Cada frente utiliza branch/worktree própria. Integração segue `develop` e depois
`main`, com remoção das branches concluídas e push executado pelo usuário.

## Contratos de integração atuais

- `src.contracts.llm.LLMClient.complete(messages, *, tools=(), tool_choice=None)`
  retorna texto opcional e chamadas nativas em `LLMResponse`.
- `src.infrastructure.llm.structured.generate_structured(client, messages,
  output_type, *, max_attempts=2)` usa
  `ChatModel.with_structured_output(..., method="function_calling")` e
  `PydanticToolsParser`, retornando `value`, `response`, `attempts`, `error_code` e `ok`.
- O schema é uma ferramenta DTO em `tools`. Não entra no prompt e não autoriza
  executar ações. Texto/JSON sem ferramenta correta é falha, sem recuperação.
- A identidade do NPC é fixada pelo servidor. Campos internos de controle,
  conquistas, fontes autorizadas e efeitos do motor não vêm do modelo.
- `tool_choice="auto"` não garante uma chamada; as opções de forcing não
  comprovadas são rejeitadas. Não afirmar constrained decoding garantido.
- Erros são sanitizados e o orçamento é finito. Auth, quota e indisponibilidade
  não recebem retries indiscriminados. Bugs e cancelamento propagam.

## Grafos e sessão

O diálogo contém autorização, guarda de entrada, contexto, geração nativa, mestre,
validação semântica, reparo limitado, guarda de saída e persistência. Cada invocação
possui estado privado; o grafo compilado não armazena mensagens entre partidas.
O ciclo social extrai relatos, revalida o mundo e agenda/avança encontros com leases
por nó e CAS. Redis/outbox continuam sendo a autoridade durável.

Fallbacks têm estado explícito e não podem virar fofoca, prova, confissão ou
conquista. Tracing externo é desativado mesmo se o host tiver LangSmith habilitado;
o admin recebe somente eventos técnicos sanitizados.

## Layout e execução

O código fica em `src/{contracts,infrastructure,modules,prompts,simulation}`, com
`src/main.py`, `src/composition.py` e `src/settings.py`. Imports usam `src.*` e o
entrypoint ASGI é `src.main:app`, sem pacote intermediário `memorias_licantropicas`.

```sh
uv sync --locked
uv run uvicorn src.main:app --host 127.0.0.1 --port 7079
uv run pytest -q
uv run python scripts/run_session_simulations.py --games 10 --api-url http://localhost:7079 --max-live-calls 200
```

## Critérios de aceitação e limites

Testes de protocolo devem verificar ferramentas no request, nome/cardinalidade,
argumentos tipados, ausência de parsing de texto, medição, cancelamento e privacidade.
O [runner atual](simulacao_partidas_refatoracao.md) substituiu a política estática
por Floriano controlado por LLM e ações HTTP na aplicação, com relógio real. O agente
recebe apenas projeções públicas e não consulta papéis secretos para decidir.
As antigas simulações com dublês foram retiradas do produto; seus resultados
continuam somente no histórico Git e não medem comportamento real do Qwen.
**O novo fluxo ainda não foi validado ao vivo no Mantle/Qwen.** Isso exige credencial
renovada e execução explicitamente limitada. Não usar AWS automaticamente nos testes.

Referências atuais: [arquitetura](refatoracao_llm.md),
[contratos](contratos_llm_estruturados.md), [grafo](grafo_dialogo_llm.md) e
[saída nativa](saida_nativa_llm.md).
