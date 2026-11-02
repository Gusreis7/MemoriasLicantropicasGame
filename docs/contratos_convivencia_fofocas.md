# Contratos de implementação da convivência

Fonte compartilhada: `contracts/social.py`. Estado privado v1 separado do catálogo v3; fichas existentes não mudam durante esta entrega. Nenhum endpoint público retorna `SocialState`.

A paráfrase sugerida pelo extrator não é conteúdo autorizado para propagação. O servidor conserva a fala inteira (até1200 caracteres), citando emissor e destinatário reais; isso mantém pronomes, perguntas e negações sem inversão de sujeito. Mensagens mais longas permanecem no histórico/literal sem propagação automática. Rótulos e pessoas sugeridos pelo extrator orientam a agenda como interpretação, sem criar fatos ou evidências.

Evolução após avaliação real do Qwen: `fala` contém a reação do personagem e `claim_ids` seleciona até dois relatos acessíveis. Se a reação não contém a proposição literal com sua fonte, o motor compõe uma citação atribuída antes de confirmar a mensagem. A mensagem final e as transmissões são persistidas juntas. IDs desconhecidos, duplicados, saída longa e divulgação privada continuam rejeitados. Isso substitui a exigência anterior de o modelo reproduzir literalmente cada citação dentro da reação. JSON puro e um único bloco JSON cercado por Markdown são aceitos; prosa adicional e chaves duplicadas são recusadas. Na extração, uma alegação estruturalmente inválida é descartada sem apagar as demais válidas do lote.

| Frente | Arquivos de propriedade |
| --- | --- |
| Memória/proveniência | `infrastructure/social_repository.py`, `modules/knowledge/**`, `tests/test_social_knowledge.py` |
| Agenda/encontros | `modules/social/service.py`, `modules/social/policy.py`, `modules/social/worker.py`, `tests/test_social_service.py` |
| Mundo/interface | `modules/world/model.py`, `modules/world/schema.py`, `modules/world/service.py`, frontend compartilhado/jogo e testes próprios |
| Integração | contratos, composição/lifespan, harness, outbox no RedisMemoryRepository, conversas, admin, rotas sociais e testes integrados |

`RedisSocialRepository(client,prefix)` implementa `SocialRepository`: CAS de revision, opcional commit conjunto do mundo, revalidação de dia/vida/liberdade/copresença e ausência de reserva do jogador. `get` sem estado retorna agregado vazio, sem escrita. `lease(game_id)` é reserva por token com prazo e comparação ao liberar, sem manter transação durante inferência. A implementação deve impedir commit de worker cujo token expirou. Eventos JSON com id/type/occurred_at/source/data seguem o registro atual.

Outbox durável: `prefix:game:{UUID}:social:exchanges`, lista append-only de `ExchangeRecord`. A integração acrescenta cada par player/NPC confirmado na mesma transação do histórico. `exchange_cursor` avança somente após processamento ou rejeição explícita. Extração processa até quatro pares consecutivos do mesmo NPC por chamada, até oito chamadas/dia; nenhuma leitura privada cruza NPCs. `KnowledgeService(repository, characters, llm, clock=None)` oferece `process_pending`, `context` e funções puras de transmissão/relação em `modules/knowledge/rules.py`; assinatura das funções puras será comunicada pela frente.

`SocialService(repository, knowledge, games, characters, world_repository, turns, llm, player_gate, clock=None)` oferece `tick(game_id)`, `interrupt(game_id,npc_id)`. `tick` executa uma unidade limitada, respeita lease e reserva curta do jogador apenas ao alterar mundo/validar commit. Nunca mantém a reserva durante LLM. Slots 60/120/180/240, até quatro falas, máximo duas participações/NPC/dia, timeout por LLM de12s e deadline do encontro de40s. Todas as chamadas são debitadas antes da inferência. Retorno de `tick` pode ser bool indicando progresso. Não repetir slots de dias encerrados.

Disponibilidade de mundo: `WorldNPC` ganha `activity` (idle/travelling/talking), `social_encounter_id`, `travel_destination_id`, `travel_arrives_at`, `social_partner_id`, todos com defaults compatíveis. SocialService grava esses campos e coordenadas em commits conjuntos. WorldService omite NPC em trânsito do local e permite abordar/interromper quem conversa; callback opcional de interrupção configurado pela integração, sem inferência. Campos públicos devem incluir somente estado visível, sem destino global oculto ou assunto.

Conversa social tem uma mensagem por turno em `Encounter.messages`; não chamar `HarnessService.respond`, que persiste pares. Geração recebe só ficha do ator, conhecimento dele e mensagens confirmadas do encontro. Rejeitar saídas inválidas e preservar somente mensagens efetivamente ditas. Transmissão de alegações e mensagem são um único CAS. Origem real e fonte alegada são distintas, raízes repetidas não somam confiança. Tarefa social não altera evidência, decisão do delegado ou papel.

Integração de diálogo: Harness recebe memória social projetada no prompt; ao abordar, a conversa social é interrompida sob a reserva do jogador antes de validar alcance. Root implementa projeção pública de relatos que Floriano efetivamente ouviu e endpoint admin autenticado para o estado social privado. Worker inicia/para no lifespan e descobre partidas pelo índice Redis existente; não inferir em GET.
