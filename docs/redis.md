# Persistência Redis

A composição cria um cliente `redis.asyncio.Redis` compartilhado com respostas decodificadas e o encerra no lifespan. Repositories guardam estado validado; o modelo não recebe acesso direto ao banco.

## Organização

O prefixo padrão é `ml:v1`, configurável por `REDIS_PREFIX`. Ele não indica a versão do formato da investigação. Os registros de uma partida usam o UUID entre chaves como hash tag Redis.

| Sufixo dentro de `<prefix>:game:{uuid}` | Conteúdo |
| --- | --- |
| `:state` | Partida e sorteio privado |
| `:investigation` | Investigação autoritativa, incluindo a mesa |
| `:table` | Projeção da mesa para inspeção, gravada na mesma transação |
| `:social` | Conhecimento, relações e proveniência |
| `:conversation:<id>` | Participantes da conversa |
| `:conversation:<id>:messages` | Mensagens por ID |
| `:conversation:<id>:order` | Ordem de inserção das mensagens |

Também existem índices de partidas/conversas, eventos, sessões administrativas, reservas, outbox e consumo. Essa tabela resume os agregados, não é uma lista completa de chaves. A [mesa determinística](mesa_deterministica.md) detalha a autoridade dos registros; o [admin](admin.md) descreve os índices de consulta.

## Consistência e isolamento

Repositories combinam operações atômicas e transações `WATCH/MULTI/EXEC`, com tentativas limitadas. IDs e payloads protegem contra duplicação e sobrescrita conflitante. O lote de mensagens é persistido inteiro; o outbox permite aplicar seus efeitos de forma idempotente.

As reservas de conversa e ação do jogador coordenam inferência e alterações incompatíveis. Elas complementam a atomicidade do armazenamento. Um conflito esgotado retorna erro, sem loop ilimitado nem gravação parcial intencional.

Leituras validam partida, participante e destinatário em contexto confiável. A API pública recebe projeções; o admin exige sessão. Isso não transforma um UUID público em autenticação de propriedade da partida. Erros de armazenamento são sanitizados e não devem devolver credenciais ou estado privado.

## Formato e durabilidade

A investigação usa formato 2; o parser rejeita registros incompatíveis. Não há adaptador para partidas antigas. A chave materializada `:table` não é uma segunda fonte independente de verdade.

Os Composes local e de produção habilitam AOF. Localmente, os dados ficam em volume Docker; na AWS, no EBS da fundação em `/srv/ml-data`. A política `everysec` pode perder aproximadamente o último segundo em uma falha e não substitui backup.

Dados de partida não têm expiração geral automática; sessões e reservas têm seus próprios prazos. O limite de histórico lido não limita o tamanho armazenado. Para operação e remoção deliberada de dados, consulte [deploy local](deploy_local.md) e [solução AWS](solucao_aws.md). Preserve backups de `artifacts/` ao limpar arquivos de desenvolvimento.
