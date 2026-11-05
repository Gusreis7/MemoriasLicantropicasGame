# Conversa jogador–persona

> Registro histórico. Para os contratos, grafos e tratamento de saídas atuais, consulte [arquitetura LLM](refatoracao_llm.md).

Implementação em `feat/conversa_jogador_persona`, partindo de `develop`. Ao concluir, o checkout retorna a `develop`; esta entrega não faz merge ou push automático. O `smoketest.py` é removido na branch da funcionalidade, substituído pelo fluxo real da API.

## Escopo e decisões

1. Criar uma conversa privada entre Floriano (`player`) e um NPC vivo da partida.
2. Receber uma mensagem e executar exatamente uma resposta do harness, usando ficha e estratégia individuais.
3. Persistir pergunta e resposta em lote e permitir consultar o histórico.
4. Proteger a conversa com reserva Redis durante a inferência.
5. Gerar token temporário pelo perfil AWS local quando não há API key explícita.

Não há interface gráfica, agendamento de encontros, avanço de dia/noite, crimes, ferramentas de ação ou cálculo de crenças nesta entrega. O Swagger em `/docs` permite exercitar o fluxo.

## Contratos e camadas

`modules/conversations/router.py` recebe HTTP e schemas; `service.py` valida a partida, o par e a elegibilidade, adquire a reserva e chama o harness. As portas de repositories continuam em `contracts/repository.py`; a infraestrutura implementa memória e reserva Redis. O harness não recebe Request ou campos de autorização do cliente.

| Operação | Entrada / saída |
| --- | --- |
| `POST /api/v1/games/{game_id}/conversations` | `{"npc_id":"capitu"}` → `201`, ID, partida, persona e criação |
| `GET /api/v1/games/{game_id}/conversations/{conversation_id}` | Metadados públicos da conversa |
| `POST .../{conversation_id}/messages` | `{"content":"..."}` → `200`, mensagem da persona |
| `GET .../{conversation_id}/messages?limit=50` | Últimas mensagens, em ordem de inserção; limite de 1 a 200 |

Mensagem pública: `id`, `speaker` (`player`/`npc`), `content`, `created_at`. O POST devolve somente a nova resposta; o GET mostra pergunta e resposta. Não retorna modelo interno de personagem, tática, objetivo ou papel. A fala livre do LLM ainda pode cometer erros; instruções de sigilo não garantem ausência de confissões indevidas.

O servidor recupera a persona pelo ID da conversa e fixa `speaker_id=player`. Campos extras como `speaker_id`, `role` ou outro `npc_id` no envio de mensagem retornam 422. Texto vazio, só espaços ou acima de 8000 caracteres também retorna 422. Partidas/conversas ausentes: 404; NPC morto ou conversa NPC–NPC: 403; versão incompatível ou mensagem simultânea: 409; falha de integração: 503.

A API permanece local e sem autenticação de usuários. A validação de participantes não substitui a futura associação de cada partida a um jogador autenticado.

## Histórico e concorrência

A memória de contexto continua restrita à conversa atual (até 20 mensagens anteriores e 24000 caracteres de histórico). Abrir outra conversa cria outro histórico; ainda não há memória automática entre encontros da mesma persona.

A reserva usa `SET NX` com token de propriedade e TTL na chave `...:conversation:<id>:busy`. Outro envio simultâneo recebe 409; não fica na fila e não chama o modelo. O tempo total da operação é limitado a `LLM_TIMEOUT_SECONDS + 10`; a reserva expira dez segundos depois desse limite. A liberação compara o proprietário sob `WATCH/MULTI`, sem remover uma reserva posterior. O estado do jogo não é bloqueado durante a inferência.

Falha do provedor não salva meia conversa. Histórico completo não é alterado por perguntas; novos pares são anexados. Não há idempotência de requisição HTTP inteira: se o cliente perder a resposta, deve consultar o histórico antes de reenviar. A reserva protege este caminho HTTP; chamadores diretos do harness ainda precisam respeitar a mesma disciplina.

## Personas e teoria dos jogos

As fichas mantêm biografias, relações e objetivos dos rascunhos. O enriquecimento acrescenta voz, prioridades ordenadas, condições de cooperação/omissão, reação à pressão e tática por papel em `modules/characters/strategies.py`. São interpretações narrativas desses interesses; não são novos fatos, pistas ou crimes canônicos.

| Persona | Incentivo e tensão principal |
| --- | --- |
| Bentinho | Quer reconhecimento da própria honra e suspeitas; teme expor espionagem, insegurança e evasão dos remédios |
| Capitu | Quer autonomia e confiança profissional; protege intimidade, clientes e desejo de separação |
| Escobar | Quer proximidade de Bentinho; protege sua paixão secreta e aparência de amizade |
| Rubião | Busca aprovação de Florença e imagem de generosidade; evita admitir a rejeição |
| Virgília | Troca informações sociais, mas protege Florença e sua tranquilidade; distingue fofoca de observação |
| Florença | Coopera quando há respeito por sua autonomia e pelo pai; confronta paternalismo e o poder de Bacamarte |
| Bacamarte | Defende autoridade científica; tende a reinterpretar perguntas como dados sobre a mente do detetive |

Aplicação dos conceitos:

- **Informação incompleta:** Floriano não conhece o papel/objetivos privados; o NPC não conhece os papéis alheios.
- **Cheap talk:** promessas, acusações e garantias verbais não alteram fatos do jogo nem provam inocência.
- **Interesses parcialmente alinhados:** colaborar pode reduzir suspeita, mas revelar intimidade ou prejudicar aliados tem custo narrativo.
- **Reputação entre interações:** manter coerência tem valor; o histórico informa o diálogo, sem implementar uma pontuação de confiança.
- **Blefe e omissão:** civis também ocultam segredos. O lobisomem consciente recebe apenas sua tática e seu objetivo ativo; um civil não recebe a tática de lobisomem.

Bacamarte em negação continua recebendo objetivo/tática civis e seus lapsos, sem a afirmação explícita de que sabe ser lobisomem. Não se resolve equilíbrio de Nash, payoff numérico ou atualização bayesiana. A adaptação é uma proposta de design, inspirada na comunicação estratégica discutida em [Cheap Talk — Farrell e Rabin](https://pubs.aeaweb.org/doi/10.1257/jep.10.3.103).

## Versão do catálogo

O catálogo passou de 1 para 2 e para 3. A versão 3 declara segredos pessoais que devem ser preservados nas falas e reforça a atribuição de relatos no prompt. Partidas novas são criadas com `content_version="3"`. Leitura pública e diálogo rejeitam versões anteriores com 409, em vez de reinterpretar fichas no meio da partida. Os dados antigos são preservados; crie outra partida. Ainda não há migração nem snapshots de versões antigas.

## AWS local e uso

As dependências de geração de token e `botocore[crt]` passam a runtime, pois agora são usadas pela API. Se `AWS_BEARER_TOKEN_BEDROCK` estiver preenchido, ele tem prioridade. Caso contrário, `AWS_PROFILE` seleciona um perfil explicitamente, sem alterar variáveis globais no servidor. O token é gerado antes de cada inferência em uma thread, tem duração solicitada de 15 minutos (limitada à sessão AWS) e não é salvo nem impresso. A criação dos serviços não resolve credenciais nem chama AWS.

```sh
uv sync --locked
docker compose up -d redis
AWS_PROFILE=terraform AWS_REGION=us-east-1 uv run uvicorn memorias_licantropicas.main:app --reload
```

Para esse caminho, a sessão AWS CLI deve estar válida. O cache do host não é montado automaticamente no container da API; execute a API no host para usar seu perfil. O Compose da aplicação continua aceitando bearer token por ambiente.

Em outro terminal, substitua os UUIDs pelos valores retornados:

```sh
curl -X POST http://localhost:8000/api/v1/games -H 'Content-Type: application/json' -d '{}'
curl -X POST http://localhost:8000/api/v1/games/GAME_ID/conversations \
  -H 'Content-Type: application/json' -d '{"npc_id":"capitu"}'
curl -X POST http://localhost:8000/api/v1/games/GAME_ID/conversations/CONVERSATION_ID/messages \
  -H 'Content-Type: application/json' -d '{"content":"O que pode me contar sobre Brás Cubas?"}'
curl http://localhost:8000/api/v1/games/GAME_ID/conversations/CONVERSATION_ID/messages
```

Os testes usam inferência simulada e gerador de token substituído, nunca credenciais reais. Cobrem as sete personas pela API, continuidade do diálogo, bloqueio de remetente forjado, conversas privadas, reservas concorrentes/expiração, versões e seleção das táticas. O usuário confirmou previamente o acesso real ao modelo pelo smoke test; nenhuma nova inferência real é necessária para esses testes.

Validação desta entrega: **81 testes aprovados com Redis em memória e 81 com Redis real em Docker**. O build da imagem da API também concluiu com `uv sync --locked --no-dev`, incluindo as dependências AWS de runtime. O Redis temporário dos testes foi removido. A nova rota não foi exercitada contra AWS real nesta execução.
