# Refatoração LLM: contratos, grafos e partidas executáveis

## Objetivo

Separar transporte Mantle, prompts versionados, parsing tipado, validação semântica,
orquestração LangGraph e persistência. Preservar o motor determinístico, a privacidade
por personagem, a medição de chamadas e os contratos REST. Push fica com o usuário.

## Frentes e contratos de integração

| Branch | Responsabilidade | Arquivos exclusivos |
| --- | --- | --- |
| feat/llm_contracts | langchain-core, dependências, parser Pydantic, erro sanitizado, geração estruturada com tentativas limitadas | pyproject.toml, uv.lock, infrastructure/llm/structured.py, novos testes de contratos |
| feat/llm_graph | grafo real de diálogo, estado por invocação, prompts de personas separados, fallback seguro e rastreável | modules/agents/*, prompts/personas, testes do harness/grafo |
| feat/llm_simulation | partidas completas executando serviços reais e diálogos, sementes, rastros e relatório | novo runner de partidas, testes e relatório de simulação |
| feat/llm_refactor | integração, mestre, conhecimento/social, documentação e limpeza comprovada | modules/session_master, modules/knowledge, modules/social, docs |

Interface comum: `infrastructure.llm.structured.generate_structured(client, messages,
output_type, *, max_attempts=2)` retorna resultado com `value`, `response`, `attempts`,
`error_code` e propriedade `ok`. Falha não contém resposta bruta, prompt ou credencial.
`parse_model_output(text, output_type)` valida JSON completo e contrato Pydantic usando
output parser do langchain-core. Não recuperar JSON de prosa, reparar truncamento,
remover campos desconhecidos ou converter tipos inesperados silenciosamente.

O transporte continua `LLMClient.complete(tuple[ChatMessage, ...]) -> LLMResponse`.
Suporte nativo a JSON Schema no Mantle/Qwen deve ser verificado em documentação oficial;
sem confirmação, não declarar geração garantida. Instruções de formato são explícitas,
parsing permanece obrigatório e cada tentativa passa pelo cliente medido existente.

Novas falas: contrato Pydantic `NpcSpeech(fala: str)`; identidade vem do servidor.
Históricos antigos podem ter leitor de compatibilidade isolado, sem contaminar geração.
O grafo deve conter geração, parsing, revisão do mestre, validação de segurança,
reparo limitado e persistência, com fallback/erro identificáveis. O estado é privado
por invocação/conversa; nenhum singleton contém mensagens de diferentes partidas.
Redis e o outbox existente continuam sendo a autoridade durável; não duplicar memória
em checkpointer independente sem estratégia de consistência.

Simulação: usar o motor e repositórios reais, relógio controlado, LLM simulado declarado,
políticas que recebem apenas projeções públicas, investigação, conversas, noites e
resultado terminal. Não fabricar vitória nem consultar o papel para escolher acusações.
Métricas offline não representam qualidade/custo real do Qwen. Modo real só por opção
explícita, com limites de chamadas; não usar credenciais AWS automaticamente nos testes.

## Integração e aceitação

Cada frente trabalha em worktree/branch própria, registra decisões e entrega commits.
Integrar em develop, verificar a suíte e partidas completas, depois promover a main,
remover branches concluídas e manter push manual. Remover somente código/artefatos sem
consumidores comprovados; relatórios históricos não são código morto.
