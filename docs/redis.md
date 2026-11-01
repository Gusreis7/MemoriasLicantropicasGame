# Persistência Redis — contratos v1

Branch da frente: `feat/redis_memorias`. Implementação em `infrastructure/redis_repository.py`, seguindo as portas de `contracts/repository.py`.

## Plano executado

1. Representar a partida sorteada como registro imutável insert-only.
2. Criar conversas com participantes fixos e namespace da partida.
3. Persistir lotes de mensagens sem gravação parcial e com deduplicação por ID.
4. Restringir leitura de histórico aos participantes e encapsular erros de Redis.

Nenhum teste, servidor Redis, Docker ou chamada AWS foi executado nesta frente, conforme solicitado. Integração de configuração, dependência, Compose e ciclo de vida da conexão pertence à coordenação.

## Construção e chaves

Injetar um cliente `redis.asyncio.Redis` com `decode_responses=True`. A conexão é compartilhada pela aplicação e encerrada no lifespan, não pelos repositories.

Construtores: `RedisGameRepository(client, prefix="ml:v1")` e `RedisMemoryRepository(client, prefix="ml:v1")`.

| Chave | Tipo | Conteúdo |
| --- | --- | --- |
| `ml:v1:game:{game_uuid}:state` | string JSON | `GameState` interno, incluindo sorteio secreto |
| `ml:v1:game:{game_uuid}:conversation:conversation_uuid` | string JSON | `Conversation`, com participantes imutáveis |
| `ml:v1:game:{game_uuid}:conversation:conversation_uuid:messages` | hash | ID da mensagem → JSON `ConversationMessage` |
| `ml:v1:game:{game_uuid}:conversation:conversation_uuid:order` | list | IDs das mensagens na ordem de inserção |

As chaves reais contêm as chaves literais ao redor do UUID da partida (`{uuid}`), como hash tag Redis. Isso coloca os registros de uma mesma partida no mesmo slot, sem pressupor suporte a cluster no cliente desta entrega. Cada partida tem namespace próprio; o prefixo é configurável e não aceita chaves.

## Operações e garantias

- `create(game)`: `SET NX`, retorna `False` se o ID existir. O sorteio não é substituído.
- `get(game_id)`: retorna estado validado ou `None`. JSON inválido/identidade divergente resulta em `StorageUnavailableError`.
- `create_conversation`: exige partida existente e dois participantes elegíveis (`player` ou NPC vivo). `WATCH` da partida e da conversa protege a criação; ID já existente retorna `False`, sem alterar participantes.
- `get_conversation`: lookup restrito ao namespace recebido; é interface interna, não endpoint público de histórico.
- `append_messages`: valida remetentes contra os participantes. Mensagens são inseridas em hash e lista na mesma transação. Repetir o mesmo ID e payload não insere outra entrada. Mesmo ID com conteúdo diferente gera `ConflictError` e não grava nenhuma parte do lote. Duplicatas dentro de um lote seguem a mesma regra.
- `list_messages`: valida o participante antes de ler; retorna as últimas mensagens em ordem de inserção, de mais antiga para mais recente no recorte, com limite padrão 20 e faixa permitida 1–200. A sequência de commit é a ordem do histórico; não se reordena por relógio do remetente. `WATCH`/`EXEC` confirma um snapshot consistente entre metadados, IDs e conteúdos.

Transações usam `WATCH`/`MULTI`/`EXEC` e no máximo cinco tentativas. Contenção esgotada gera `ConflictError`, sem loop ilimitado. Falhas de Redis são convertidas em `StorageUnavailableError` com mensagem genérica, sem respostas brutas, credenciais ou estado secreto.

Autorização de leitura é baseada em `viewer_id`, que é parâmetro de serviço interno e deve vir de contexto confiável. Isso não implementa autenticação de jogador. O repository não interpreta mensagens nem permite que elas mudem participantes, papéis ou estado do mundo.

## Durabilidade e retenção

Os repositories não aplicam TTL, expiração ou remoção automática. Isso evita apagar evidências silenciosamente; retenção e exclusão de partidas ficam para uma entrega com política explícita.

Para desenvolvimento, a integração deve habilitar AOF e volume persistente do Redis no Compose. A durabilidade final depende da configuração do servidor (por exemplo, `appendfsync everysec` pode perder aproximadamente o último segundo em uma falha). Redis não substitui uma estratégia de backup. Este código não realiza exportação, backup ou restauração por conta própria.

Não há busca vetorial, índice global de partidas, paginação por cursor, compactação ou edição de mensagens. O tamanho total de um histórico ainda não possui quota de armazenamento. O limite de leitura limita o contexto carregado, não a retenção.

## Limites de concorrência

O append atômico evita misturar metade de dois pares de mensagens. Não serializa a inferência inteira: duas respostas geradas a partir do mesmo histórico podem ser persistidas em sequência. O harness deve aguardar cada resposta na base atual. Um futuro controle de turno/conversa poderá acrescentar reserva de execução e idempotência de requisição; isso não é prometido por esta interface.
