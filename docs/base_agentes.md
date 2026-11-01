# Integração da base de agentes

## Entrega e branches

O trabalho foi dividido antes da implementação, com interfaces comuns em [contratos_agentes.md](contratos_agentes.md). Cada agente implementa e registra sua frente em uma branch/worktree separada:

- `feat/contratos_agentes`: planejamento prévio e contratos v1.
- `feat/personagens_sorteio`: catálogo e API REST de personagens/partidas.
- `feat/redis_memorias`: persistência assíncrona de partidas e interações.
- `feat/harness_mantle`: projeção privada do NPC, diálogo e cliente Bedrock.
- `feat/base_agentes`: composição e integração local das frentes, ambiente, dependências e Compose.

A integração inicial utilizou merges locais das branches de trabalho na branch de integração. Depois da autorização do usuário, a base foi integrada em `develop` pelo commit `2c74c24`, e as branches/worktrees concluídas foram removidas. `main` e o remoto permanecem sem alterações. As decisões de cada frente ficam em [personagens_sorteio.md](personagens_sorteio.md), [redis.md](redis.md) e [harness.md](harness.md).

| Frente | Commit de entrega |
| --- | --- |
| Contratos e planejamento | `eb80090` |
| Personagens e sorteio | `af14a9c` |
| Redis e memórias | `cdb515f` |
| Harness e Mantle | `ea1f8c2` |
| Configuração e composição | `456d16a` |

As três frentes foram integradas sem conflitos. O lockfile foi atualizado com uv; foram revisados estaticamente os imports e assinaturas usados na composição, as projeções públicas e as regras de visibilidade da memória. Essa revisão não substitui testes de execução.

## Configuração

Copiar `.env.example` para `.env`. uv continua sendo o gerenciador de dependências; `pyproject.toml` e `uv.lock` incluem cliente Redis, httpx e configuração Pydantic. Não há dependência do SDK OpenAI: o adaptador faz Chat Completions via HTTP ao endpoint Mantle.

| Variável | Padrão | Uso |
| --- | --- | --- |
| `REDIS_URL` | `redis://localhost:6379/0` | Desenvolvimento fora do container; Compose usa `redis://redis:6379/0` |
| `REDIS_PREFIX` | `ml:v1` | Namespace das chaves |
| `AWS_REGION` | `us-east-1` | Região usada para construir a URL padrão |
| `AWS_BEARER_TOKEN_BEDROCK` | vazio | API key Bedrock; necessária somente ao inferir |
| `BEDROCK_MODEL` | `qwen.qwen3-32b` | Modelo de diálogo |
| `BEDROCK_BASE_URL` | derivada da região | Raiz `https://bedrock-mantle.{region}.api.aws/v1` |
| `LLM_TIMEOUT_SECONDS` | `30` | Timeout HTTP por inferência |
| `LLM_MAX_TOKENS` | `512` | Limite de saída por resposta |
| `LLM_HISTORY_LIMIT` | `20` | Máximo de mensagens anteriores incluídas no prompt |

O adaptador inicial usa bearer token Bedrock, não credenciais de Qwen Cloud ou SigV4. Uma chave vazia não impede iniciar a aplicação, listar personagens ou sortear partidas. A tentativa de diálogo sem chave retorna erro de integração sem salvar pergunta/resposta parcial.

O modelo configurado corresponde ao Qwen3 32B listado pela AWS para Mantle. A elegibilidade do free tier/créditos é específica da conta; não foi consultada e não é garantida pela configuração. Referências: [modelo](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-qwen-qwen3-32b.html) e [preços](https://aws.amazon.com/bedrock/pricing/).

## Recursos e inicialização

`main.create_app()` registra routers e trata erros compartilhados. O lifespan cria os serviços em `composition.build_services(Settings())`, atribui a `app.state.services` e fecha clientes no shutdown. Nenhum ping Redis ou chamada AWS é feito pelo lifespan. O Compose aguarda o healthcheck do Redis antes de iniciar a API; `/health` informa apenas a saúde do processo, não a disponibilidade das dependências.

O Redis usa volume `redis_data`, AOF com sincronização a cada segundo e política `noeviction`. Isso permite persistência local, mas não substitui backup nem garante perda zero em falha abrupta. Não há TTL automático; retenção e expurgo ficam para evolução futura. Não executar `docker compose down -v` para manutenção comum.

## Uso da API

Após preparar o ambiente e iniciar os serviços:

```sh
curl http://localhost:8000/api/v1/characters
curl -X POST http://localhost:8000/api/v1/games \
  -H 'Content-Type: application/json' -d '{}'
curl http://localhost:8000/api/v1/games/UUID_DA_PARTIDA
```

O POST usa o elenco completo e sorteia no servidor com uma fonte não controlada pelo jogador. Campos como `seed`, `werewolf_id` e `role` não são aceitos. Respostas incluem somente a projeção pública, nunca os modelos privados dos contratos. Catálogo funciona sem conectar Redis; criação/consulta de partida depende de Redis.

Erros de domínio usam `{"detail": "..."}`: 404 para ausência, 403 para acesso indevido, 409 para conflito e 503 para integração indisponível. UUID inválido e corpo fora do schema resultam em validação 422 do FastAPI.

## Uso interno do harness

O serviço ainda não é uma rota HTTP. Após criar uma partida, um chamador interno pode usar `services.harness.respond(game_id, npc_id, conversation_id, speaker_id, text)`. Os IDs de partida e conversa são UUIDs; `npc_id` é o NPC que responde; `speaker_id` é `player` ou outro NPC vivo da mesma partida.

O mesmo UUID de conversa mantém o mesmo par de participantes. Outra combinação exige uma nova conversa. O serviço consulta o histórico privado, projeta apenas a ficha e o objetivo ativo do NPC, gera uma resposta e persiste pergunta/resposta juntas. Nenhum encontro é gerado automaticamente. O retorno contém a mensagem e metadados de consumo para futura observabilidade.

Uma instância lógica de NPC é identificada pelo par `(game_id, npc_id)`, com seu papel na partida e acesso somente às conversas em que participa. A memória desta base é o histórico da conversa atual; ainda não recupera automaticamente outros encontros, produz resumos ou atualiza crenças. Isso será desenvolvido antes de simular uma rede autônoma.

## Limites assumidos e validação pendente

- A entrega inicial teve apenas revisão estática. Posteriormente, a suíte descrita em [testes.md](testes.md) foi executada com Redis em memória e Redis real em container. Build da imagem da API e inferência AWS continuam sem validação.
- API local sem autenticação, autorização por jogador ou rate limiting. Não é um serviço multiusuário publicado.
- Sem progressão de dias/noites, crimes, pistas, acusação, encontros autônomos ou ferramentas de ação.
- Sem execução concorrente serializada por conversa; o chamador deve aguardar uma resposta antes de iniciar a próxima. Atomicidade de armazenamento não torna a inferência idempotente.
- Sem replay completo, backup, expurgo, telemetria persistida ou testes de carga.
- O catálogo possui versão, mas não há migração entre versões de conteúdo. Não editar fichas de uma versão mantendo partidas antigas como se fossem compatíveis.

Os testes agora verificam sorteio secreto, persistência, nova conexão ao mesmo servidor, visibilidade e contratos HTTP. Continuam pendentes o build da imagem da API, a recuperação após reinício do servidor Redis e uma inferência Mantle com as credenciais e limites da conta.
