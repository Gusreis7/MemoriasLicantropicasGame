# Saída nativa de agentes: ferramentas e LangChain

O contrato estruturado agora é uma ferramenta DTO declarada no parâmetro `tools`
do Chat Completions Mantle. Não há schema anexado ao system prompt, pedido de JSON,
extração de `message.content`, correção de cercas ou parser de JSON parcial.
Os dados de ferramenta não executam ações: são propostas que passam pelo motor.

## Fluxo executado

1. O schema Pydantic é convertido por `convert_to_openai_tool` do langchain-core.
2. `MantleChatModel`, um `BaseChatModel` assíncrono, recebe
   `.with_structured_output(schema, method="function_calling", include_raw=True)`.
3. O port medido envia `tools` e `tool_choice="auto"` ao Mantle. Os prompts de domínio
   permanecem inalterados. O bearer é obtido novamente por chamada quando usa provider.
4. O adaptador recebe `message.tool_calls`. O parser de protocolo do LangChain
   (`default_tool_parser`) decodifica `function.arguments`; não lê JSON do texto da fala.
5. `PydanticToolsParser` do LangChain valida os argumentos contra o modelo. O gerador
   exige exatamente uma chamada do nome esperado e nenhuma chamada inválida.
6. Ausência de ferramenta, nome diferente, chamadas extras e erros de schema são
   falhas explícitas. Uma resposta textual contendo JSON válido também é rejeitada.

O método público `with_structured_output` é especializado para este provedor usando
`bind_tools(..., tool_choice="auto") | PydanticToolsParser`. O método padrão do
BaseChatModel usa `any`; este bridge não mapeia silenciosamente uma solicitação de
forcing para `auto`. Chamadores que pedem `required`, `any`, ferramenta nomeada ou
`json_mode` recebem erro de configuração antes de chamar o provedor.

## Port e tipos

`LLMClient.complete(messages, *, tools=(), tool_choice=None) -> LLMResponse`.
Cada `NativeToolCall` tem `name`, `args` (dict), `id` e `type="tool_call"`.
`invalid_tool_calls` mantém falhas do protocolo com erro estável. `content` pode ser
vazio quando há ferramenta; seu conteúdo e os argumentos não aparecem em `repr`.
O `MeteredLLMClient` encaminha as opções e contabiliza cada chamada real.

Tuplas de contratos wire aceitam arrays por `Field(strict=False)` no contêiner;
UUIDs wire aceitam strings por anotação de campo. Escalares continuam strict e
campos adicionais continuam proibidos. Isso permite o `PydanticToolsParser` padrão,
sem override de parser privado ou conversão JSON de ida e volta.

`generate_structured` preserva `value`, `response`, `attempts`, `error_code` e `ok`.
Códigos de falha nativa: `invalid_tool_response`, `invalid_tool_arguments` e
`invalid_schema`. Auth/quota/rede não repetem; formato inválido admite uma a três
tentativas, padrão duas. Nenhuma resposta rejeitada é anexada ao próximo prompt.
Cancelamento e erros inesperados continuam propagando. O bridge possui uma pequena
adaptação explícita na fronteira de cancelamento do BaseChatModel 1.7: cancelamentos
originados pelo transporte atravessam o tratamento batch do framework e são
restaurados como `CancelledError`, inclusive em invocação direta do ChatModel.
Testes também cancelam uma task real para verificar que não há fallback ou retry.

A execução do Runnable ocorre dentro de `tracing_context(enabled=False, parent=False)`.
Assim variáveis LangSmith incidentais do host não exportam prompts, personas ou
argumentos. Observabilidade do jogo continua nos registros próprios sanitizados.

## Suporte confirmado e limites

A [ficha AWS do Qwen3 32B](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-qwen-qwen3-32b.html)
lista **client-side tool calling** no Mantle, com modelo `qwen.qwen3-32b` e endpoint
`https://bedrock-mantle.{region}.api.aws/v1`. O projeto mantém esse modelo/endpoint.

A [documentação AWS de ferramentas client-side](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html)
distingue `auto` de opções que forçam uma chamada: forcing não é suportado por todos
os modelos. Não foi comprovado forcing para este par Mantle/Qwen, portanto esta
entrega usa `auto` e falha se o modelo responder sem ferramenta. Não promete
constrained decoding ou emissão garantida de chamada em todas as respostas.

As fontes de integração são a [referência BaseChatModel](https://reference.langchain.com/python/langchain-core/language_models/chat_models/BaseChatModel),
[o parser de ferramentas Pydantic](https://reference.langchain.com/python/langchain-core/output_parsers/openai_tools/PydanticToolsParser)
e [o guia LangChain de tool calling](https://www.langchain.com/blog/tool-calling-with-langchain).

Os testes usam `httpx.MockTransport`, clientes simulados e o Runnable real. Eles
verificam o protocolo, schema, erros, renovação do bearer, medição e privacidade;
**não são inferências reais do Qwen**. Não houve nova chamada paga nesta correção.
