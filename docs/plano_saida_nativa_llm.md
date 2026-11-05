# Correção: saída nativa, layout src e ausência de regex

Decisão do usuário: código diretamente em `src/`, sem o pacote intermediário
`memorias_licantropicas`; remover `re` do aplicativo e remover pedidos de JSON dos
prompts. A saída estruturada deve usar o protocolo de ferramentas do provedor,
LangChain ChatModel/with_structured_output e output parser de ferramentas tipado.
O grafo LangGraph permanece responsável por sessões, validações e falhas explícitas.

Frentes isoladas:

- `feat/native_llm_provider`: transporte Mantle/ChatModel, contrato de tool calls,
  parser PydanticToolsParser e testes HTTP/SDK; sem extração de texto ou formato no prompt.
- `feat/native_text_validation`: remover regex dos validadores/guardas/regras,
  preservando autoria, autorização e regressões com operações de texto explícitas.
- `feat/native_simulation_clients`: migrar dublês e clientes de simulação/testes
  para envelopes de ferramenta reais; JSON em texto deve ser rejeitado.
- Integração: limpar prompts, retirar parser textual legado, aplicar layout
  `src/{main.py,composition.py,settings.py,contracts,infrastructure,modules,prompts,simulation}`,
  atualizar imports/entrypoints/build, validar e integrar develop → main sem push.

Contrato de transporte compartilhado: `LLMClient.complete(messages, *, tools=(),
tool_choice=None) -> LLMResponse`. `LLMResponse` terá `content` opcional vazio e
`tool_calls`/`invalid_tool_calls` compatíveis com `AIMessage`. Cada ferramenta tem
nome e argumentos já estruturados pelo protocolo. As ferramentas de saída são
DTOs; não executam comandos do jogo, shell ou infraestrutura.

A função `generate_structured` mantém sua interface pública/resultados e orçamento,
mas usa ChatModel.with_structured_output + output parser nativo, sem instruções
JSON, cercas Markdown, regex ou recuperação de texto. Respostas sem ferramenta
correta são falhas explícitas; não há downgrade para JSON solicitado em prompt.

Todos trabalham inicialmente no layout atual para evitar conflitos mecânicos.
O coordenador fará a movimentação e a alteração de imports após integrar as frentes.
Credencial AWS estava expirada na última consulta. Esta etapa não executa chamadas
pagas; testes de protocolo não serão apresentados como validação do Qwen real.
