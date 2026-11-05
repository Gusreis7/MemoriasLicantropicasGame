# Contratos nativos de geração

A referência de implementação e suporte do provedor está em
[saída nativa LLM](saida_nativa_llm.md). Esta página descreve as interfaces usadas
pelos serviços no layout `src/`.

## Transporte e ferramentas

`src.contracts.llm.LLMClient.complete(messages, *, tools=(), tool_choice=None)`
retorna `LLMResponse`. O schema Pydantic é declarado como uma ferramenta DTO no
parâmetro `tools` do Mantle; não é anexado às instruções da persona.

| Campo de transporte | Significado |
| --- | --- |
| `content` | Texto opcional do envelope do provedor; não é fonte de saída estruturada |
| `tool_calls` | Chamadas nativas com `name`, `args` estruturados, `id` e `type="tool_call"` |
| `invalid_tool_calls` | Argumentos inválidos no protocolo, com código sanitizado |
| `model`, `input_tokens`, `output_tokens` | Modelo e consumo retornados pelo provedor |

Conteúdo e argumentos são omitidos de `repr`. Nenhuma dessas ferramentas executa
shell, alteração de papel, ação do jogador ou efeito do mundo. Elas representam
propostas; identidade e autorização continuam sendo decisões do servidor.

## LangChain e validação

`src.infrastructure.llm.structured.MantleChatModel` implementa o `BaseChatModel`
assíncrono. O fluxo chama
`.with_structured_output(schema, method="function_calling", include_raw=True)`
e compõe `bind_tools(..., tool_choice="auto")` com `PydanticToolsParser`.
O parser de protocolo do LangChain decodifica `function.arguments`; o parser
Pydantic verifica tipos, limites e campos permitidos.

O gerador exige exatamente uma ferramenta do nome esperado, sem chamadas inválidas.
Ausência de ferramenta, nome inesperado e chamadas adicionais falham. Uma resposta
que contenha JSON em `content` também falha, mesmo que o texto seja sintaticamente
válido. Não há pedido de formato no system prompt, extração textual, regex,
normalização de cercas ou recuperação de documentos truncados.

Os modelos proíbem campos adicionais e mantêm escalares estritos. Contêineres wire
de tuplas aceitam arrays, e campos UUID aceitam strings, pelas anotações explícitas
desses campos. Assim o `PydanticToolsParser` padrão recebe dados naturais do
protocolo, sem hook privado de parser ou conversão JSON de ida e volta.
Um lote inválido é rejeitado inteiro. Validação semântica posterior verifica
mensagens de origem, citações literais, fontes, IDs autorizados e estado do mundo.

## Resultado e orçamento

`generate_structured(client, messages, output_type, *, max_attempts=2)` retorna
`StructuredResult[T]`:

| Campo | Significado |
| --- | --- |
| `value` | Modelo Pydantic validado, ou `None` |
| `response` | Última resposta de transporte disponível; não aparece em `repr` |
| `attempts` | Número de chamadas realizadas |
| `error_code` | Código estável ou `None`, sem mensagem bruta do provedor |
| `ok` | Valor presente e ausência de erro |

Falhas de protocolo usam `invalid_tool_response`, `invalid_tool_arguments` ou
`invalid_schema`. Elas admitem nova chamada dentro do orçamento, de uma a três
tentativas; o padrão é duas. O transporte também distingue resposta truncada ou
inválida. Auth, credenciais, quota, rede e timeout não recebem retry indiscriminado.
Os prompts de domínio e o schema permanecem os mesmos; a resposta rejeitada não é
reenviada ao modelo.

O resultado não fabrica um modelo vazio. O domínio decide seu fallback e o registra
explicitamente. Cancelamento e bugs inesperados propagam. Cada tentativa atravessa
o cliente medido, incluindo chamadas cujo protocolo foi recebido mas depois
rejeitado. `completed` no medidor significa transporte concluído, não aprovação da
fala; o grafo registra a decisão de aceitação ou fallback separadamente.

## Privacidade e suporte

O Runnable é executado dentro de `tracing_context(enabled=False, parent=False)`.
Variáveis LangSmith incidentais do host não habilitam exportação de prompts,
personas ou argumentos. O jogo utiliza traces locais sanitizados e separados da
memória narrativa.

O projeto mantém **Qwen3 32B no Bedrock Mantle**. O suporte documentado a ferramentas
client-side justifica o protocolo escolhido. `tool_choice="auto"` não garante que
o modelo emitirá uma chamada; a ausência dela é tratada como falha, sem downgrade
para texto. Opções de forcing não comprovadas para o par modelo/endpoint são
rejeitadas pelo bridge.

**O novo caminho nativo ainda não foi validado com Qwen ao vivo.** Os testes de
protocolo usam HTTP MockTransport e clientes simulados com o Runnable real. Eles
não comprovam fluência narrativa, taxa real de chamadas nativas, latência ou custo
AWS. As fontes oficiais e esses limites estão em [saida_nativa_llm.md](saida_nativa_llm.md).
