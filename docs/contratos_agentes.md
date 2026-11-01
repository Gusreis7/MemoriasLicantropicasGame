# Contratos v1 e divisão de trabalho

## Escopo desta entrega

Base de personagens, sorteio secreto, memória Redis e harness de diálogo com Qwen3 32B via Mantle. Sem resolver turnos, crimes, pistas, votação, encontros automáticos ou outras mecânicas avançadas. Não executar testes, Docker ou inferências nesta entrega, conforme pedido do usuário. Atualizar lockfile é preparação de dependências, não validação de execução.

## Plano por agente de implementação

| Responsável | Branch | Plano e arquivos sob responsabilidade |
| --- | --- | --- |
| Coordenação | `feat/contratos_agentes` | Preservar planejamento existente, definir contratos Python e regras de integração neste documento |
| Personagens e partidas | `feat/personagens_sorteio` | Criar catálogo versionado a partir das referências; routers/schemas/services/repository do catálogo e de partidas; documentar rotas em `docs/personagens_sorteio.md` |
| Persistência | `feat/redis_memorias` | Implementar `RedisGameRepository` e `RedisMemoryRepository` em `infrastructure/redis_repository.py`; documentar chaves e atomicidade em `docs/redis.md` |
| Harness | `feat/harness_mantle` | Implementar adaptador assíncrono em `infrastructure/llm/bedrock_mantle.py` e `modules/agents/service.py`; documentar contexto e limitações em `docs/harness.md` |
| Coordenação | `feat/base_agentes` | Integrar commits das frentes, configurar dependências, Compose, lifespan/injeção FastAPI, tratamento de erros e instruções de uso |

As frentes partem do commit de contratos e trabalham em worktrees isoladas. Cada uma registra seu commit na própria branch. Integração ocorre somente em `feat/base_agentes`, preservando as branches de origem; nenhuma promoção para `develop` ou `main`, nem publicação remota nesta entrega. O repositório possui apenas `main` no início; o futuro fluxo passa por `develop` após aprovação.

## Modelos e interfaces

Fonte executável: `src/memorias_licantropicas/contracts/`. Os modelos são internos, imutáveis e rejeitam campos extras. Schemas públicos são separados.

- `CharacterProfile`: ID estável, nome, biografia, personalidade, objetivo civil, objetivo lobisomem e consciência do papel (`aware`/`denial`). IDs: `bentinho`, `capitu`, `escobar`, `rubiao`, `virgilia`, `florenca`, `bacamarte`.
- `GameState`: UUID, data UTC, versão do conteúdo e elenco com exatamente um lobisomem. Só os sete suspeitos são elegíveis; Floriano usa ID reservado `player`; Brás Cubas é referência narrativa.
- `CharacterRepository`: catálogo assíncrono `list/get`.
- `GameRepository`: `create` insert-only com retorno booleano e `get`; não existe atualização do papel nesta versão.
- `Conversation`: UUID, partida, dois participantes distintos e criação UTC. IDs e participantes são imutáveis. `player` ou IDs de NPCs vivos da partida; o harness valida essa elegibilidade.
- `MemoryRepository`: criar/obter conversa, anexar lote de mensagens atomicamente e recuperar histórico restrito a participante. Métodos recebem `game_id` para impedir cruzamento entre partidas.
- `ConversationMessage`: UUID, remetente, texto de até 8000 caracteres e data UTC. Deduplicação por ID; o mesmo ID com payload diferente gera conflito.
- `LLMClient.complete(tuple[ChatMessage, ...]) → LLMResponse`: texto e metadados de uso; não recebe repositories, credenciais em mensagens ou estado global da partida.
- `HarnessService.respond(game_id, npc_id, conversation_id, speaker_id, text) → HarnessReply`: serviço interno; recebe repositories e `LLMClient` no construtor, valida existência e participantes, monta contexto individual e persiste pergunta/resposta em lote após inferência bem-sucedida. Conversa inexistente pode ser criada pelo serviço; existente deve ter exatamente o par solicitado. Limite inicial: 20 mensagens anteriores. `speaker_id` também pode ser outro NPC; nenhum encontro é disparado automaticamente.

Falhas compartilhadas: `NotFoundError`, `AccessDeniedError`, `ConflictError`, `StorageUnavailableError`, `LLMUnavailableError`. A API traduz para HTTP; repositories e harness não dependem de FastAPI. Nenhum erro público deve expor resposta bruta do provedor ou segredo do jogo.

## Limites de visibilidade e execução

O harness consulta o estado real apenas para construir uma projeção privada do NPC atual. O prompt não contém o elenco com papéis, objetivos dos outros nem conversas das quais o NPC não participou. Bacamarte não recebe afirmação explícita de que sabe ser lobisomem quando em negação. Texto citado é dado de conversa, não autorização para mudar instruções ou executar ações.

O harness inicial faz uma inferência limitada por resposta, sem execução de ferramentas nem efeitos no mundo. O contrato de tool calling será ampliado quando existirem ações de jogo validadas; não criar ferramentas arbitrárias agora. O serviço suporta contextos distintos por NPC sem processos dedicados.

A base não promete idempotência de uma requisição de inferência inteira nem execução concorrente serializada por conversa. Redis deduplica mensagens por ID e persiste pares atomicamente. Clientes devem aguardar a resposta antes da próxima mensagem; locks/replay de requisição são evolução posterior explícita.

## Configuração de integração

A coordenação fornece `Settings` com `redis_url`, `redis_prefix`, `aws_region`, `bedrock_api_key`, `bedrock_base_url`, `bedrock_model`, `llm_timeout_seconds`, `llm_max_tokens`, `llm_history_limit`. Segredos via ambiente; sem chamada AWS ou ping Redis na inicialização. `GET /health` mede apenas o processo.

Construtores combinados: `RedisGameRepository(client, prefix="ml:v1")`, `RedisMemoryRepository(client, prefix="ml:v1")`; `BedrockMantleClient(*, base_url, api_key, model, timeout_seconds, max_tokens)`; `HarnessService(characters, games, memory, llm, history_limit=20)`. Adaptador tem `async aclose()`.

API desta entrega: catálogo público em `/api/v1/characters` e `/api/v1/characters/{character_id}`; criação e leitura pública de partidas em `/api/v1/games` e `/api/v1/games/{game_id}`. `get_character_service` e `get_game_service` definidos nos respectivos routers permitem injeção pela composição. Sorteio usa fonte aleatória do servidor sem seed fornecida pelo jogador; resposta jamais inclui papéis ou objetivos secretos.

O harness permanece serviço interno; não expor `speaker_id` arbitrário em endpoint público. Autenticação e propriedade de partidas ainda não implementadas: API para desenvolvimento local, sem publicar como serviço multiusuário.

## Modelo e gratuidade

Modelo padrão: `qwen.qwen3-32b`; raiz Mantle `https://bedrock-mantle.{region}.api.aws/v1`, usando Chat Completions. Autenticação inicial por API key Bedrock (bearer), configurável; não é uma API key Qwen Cloud. Credenciais AWS convencionais/SigV4 não são implementadas nesta base.

A ficha da AWS confirma o modelo no Mantle. A documentação de preços lista cobrança de inferência; não confirma gratuidade permanente para esse modelo. O enquadramento no free tier/créditos da conta do usuário deve ser confirmado quando as credenciais forem configuradas. Nenhuma inferência ou verificação de conta será feita nesta entrega.

Referências: [Qwen3 32B](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-qwen-qwen3-32b.html) e [preços do Bedrock](https://aws.amazon.com/bedrock/pricing/).
