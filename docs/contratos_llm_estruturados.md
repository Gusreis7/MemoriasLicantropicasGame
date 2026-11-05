# Contratos estruturados e limites do provedor

## Interfaces

`LLMClient.complete(messages) -> LLMResponse` continua sendo apenas o transporte.
`generate_structured(client, messages, output_type, max_attempts=2)` usa esse cliente
sem substituí-lo: as tentativas continuam passando pela medição existente.

O resultado imutável `StructuredResult[T]` contém:

| Campo | Significado |
| --- | --- |
| `value` | Modelo Pydantic validado, ou `None` |
| `response` | Resposta de transporte disponível, inclusive última inválida; não aparece em `repr` |
| `attempts` | Número de chamadas realizadas |
| `error_code` | Código estável ou `None`; nunca mensagem bruta do provedor |
| `ok` | Valor presente e ausência de erro |

Não há fallback implícito para um modelo vazio. Cada domínio decide o comportamento
quando `ok` for falso: resposta pública segura, avaliação local conservadora ou
operação adiada. A falha continua distinguível por `error_code`. Problemas de
configuração do próprio chamador e exceções inesperadas de programação propagam.

## Parsing e tipos

`StrictPydanticOutputParser` estende o `PydanticOutputParser` do **langchain-core**.
Uma etapa lexical anterior exige um documento JSON completo e um objeto na raiz.
Prosa externa, Markdown, documentos concatenados, truncamento, chaves duplicadas
(inclusive aninhadas), NaN e Infinity são rejeitados. Não se usa regex para procurar
JSON ou reparar sintaxe.

A validação Pydantic usa `model_validate_json(strict=True, extra="forbid")`, inclusive
nos modelos aninhados. Isso preserva a representação JSON de arrays para tuplas e
strings para UUIDs, mas rejeita string numérica em campo inteiro, booleano como
inteiro, campos adicionais e elementos inválidos. Um lote inválido não é parcialmente
silenciado pelo parser. Regras de autoria, referências permitidas e verdade do jogo
continuam sendo validação semântica do domínio após o parsing.

O hook `_parse_obj` do parser LangChain evita que seu caminho padrão de validação
Python rejeite arrays válidos em modelos strict com tuplas. O lockfile fixa a versão;
os testes cobrem essa integração e o comportamento de rejeição.

## Tentativas, erros e privacidade

O orçamento aceito é de uma a três tentativas; o padrão é duas. Cada chamada recebe
instruções geradas pelo parser para o mesmo schema que será validado. A instrução
entra em uma mensagem system própria antes do último user, sem alterar JSONs de
persona ou anexar dados depois de suas fichas.

Somente falhas de contrato/formato (`invalid_json`, `invalid_schema`,
`llm_invalid_response`, `llm_response_truncated`) recebem nova tentativa. Erros de
autenticação, ausência de credenciais, limite de uso, rede, modelo e timeout retornam
imediatamente. Cancelamento não é convertido em resposta ou retry. A tentativa de
reparo não reenvia texto rejeitado, traceback ou mensagens de erro do provedor.

Transportes que retornaram texto inválido ainda podem ter sido cobrados: ambas as
chamadas permanecem no medidor. `completed` nesse medidor significa transporte
concluído, não aprovação semântica da fala. Tokens de fixtures offline não são
consumo AWS.

## Mantle / Qwen3 32B

Consulta à documentação oficial em **2026-11-05**:

- A [ficha AWS do Qwen3 32B](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-qwen-qwen3-32b.html)
  distingue `qwen.qwen3-32b` no Mantle de `qwen.qwen3-32b-v1:0` no runtime. Ela lista
  structured outputs nas capacidades do runtime e client-side tool calling no Mantle.
- A [documentação de saídas estruturadas do Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html)
  descreve garantias para APIs/features específicas; isso não comprova suporte de
  `response_format/json_schema` no par Mantle Chat Completions + Qwen deste projeto.
- A [referência Chat Completions AWS](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions.html)
  consultada não estabeleceu esse suporte para o par utilizado.

Consequentemente, esta entrega mantém o endpoint/modelo existente, com schema por
instruções e validação posterior. **Não anuncia constrained decoding ou geração
nativa garantida**. Ativar um parâmetro não confirmado ou trocar silenciosamente
para runtime quebraria o contrato de infraestrutura e credenciais do projeto.

Dependências resolvidas: **langchain-core 1.7.6**, **langgraph 1.2.20** (Python 3.13),
com versões transitivas fixadas em `uv.lock`. O pacote `langchain-core` fornece o
parser e os componentes de prompts, sem adicionar o pacote agregador `langchain`.

Referências de integração: [PydanticOutputParser](https://reference.langchain.com/python/langchain-core/output_parsers/pydantic/PydanticOutputParser)
e [Graph API LangGraph](https://docs.langchain.com/oss/python/langgraph/graph-api).
