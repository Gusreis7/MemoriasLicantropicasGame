# Suíte de testes da base

Implementada em `feat/test_suits`, criada a partir de `develop` após a integração da base. A branch de testes segue para `develop` após a execução bem-sucedida e é removida depois do merge, conforme solicitado. As branches anteriores e suas worktrees limpas já foram removidas após integração. Não houve alteração em `main` nem push.

## Cobertura

| Arquivo | Comportamentos verificados |
| --- | --- |
| `test_games.py` | Todos os sete suspeitos podem ser sorteados; exatamente um lobisomem; elenco inválido, vazio ou duplicado; conflito na criação; partida ausente |
| `test_api.py` | Criação e leitura pública de partida; catálogo; sorteio não exposto; cliente não pode enviar seed ou papel; isolamento entre partidas; respostas 404/422/503; saúde e OpenAPI |
| `test_redis.py` | Insert/roundtrip; proibição de sobrescrita; inserts concorrentes; nova conexão; namespaces; dados corrompidos; falha de conexão; participantes elegíveis; append e deduplicação; rejeição atômica de lote conflitante; histórico limitado e privado |
| `test_harness.py` | Par pergunta/resposta; contexto do encontro anterior; sigilo dos objetivos alheios; negação de Bacamarte; validação do interlocutor; NPC–NPC; falha de inferência sem mensagens parciais; texto inválido |
| `test_mantle.py` | URL, bearer token, modelo e payload Chat Completions; texto e consumo retornados; status 401/429/500; saída inválida/truncada; ausência de credencial sem enviar HTTP |
| `test_conversations.py` | Fluxo HTTP com os sete NPCs, continuidade do histórico, bloqueio de spoofing, falhas, simultaneidade e versão do catálogo |
| `test_conversation_gate.py` | Reserva compartilhada, liberação, expiração e proteção contra liberação por proprietário antigo |
| `test_aws_credentials.py` | Perfil e região enviados ao gerador de token; falhas sanitizadas, sem AWS real |

O sorteio é controlado somente em testes parametrizados para verificar cada resultado possível de forma determinística. Não se faz uma asserção estatística sujeita a flutuações aleatórias. Na aplicação a fonte continua sendo `secrets.choice`.

## Execução rápida

```sh
uv sync --locked
uv run pytest -q
```

Usa `fakeredis` em memória e os repositories reais da aplicação. Não exige Docker, Redis externo ou credenciais AWS. Async tests usam o backend asyncio do plugin AnyIO; as chamadas à API usam transporte ASGI e o lifespan da aplicação com dependências de teste.

## Integração com Redis real

```sh
docker compose -p ml-test-suits -f compose.test.yaml up -d --wait
uv run pytest -q --redis-url redis://127.0.0.1:16379/0
docker compose -p ml-test-suits -f compose.test.yaml down
```

O Compose de teste é independente do Compose da aplicação, usa a porta local 16379 e não monta volumes. O servidor é descartável e não testa AOF/recuperação de disco. A opção `--redis-url` (ou variável `TEST_REDIS_URL`) substitui apenas o backend de armazenamento: executa os mesmos testes de API, repositories e harness sobre o Redis real.

Cada teste cria um prefixo exclusivo `ml:test:<uuid>`. O teardown remove somente chaves desse prefixo e fecha conexões; não usa `FLUSHDB` ou `FLUSHALL`. Não apontar os testes para um servidor de produção. Uma URL explícita inválida falha a execução, sem fallback silencioso para memória.

## Ausência de chamadas AWS

O LLM do harness é um substituto determinístico. O cliente Mantle é exercitado com `httpx.MockTransport`, incluindo inspeção de requisições e respostas simuladas. Uma fixture automática bloqueia HTTP assíncrono externo: só permite transportes ASGI e MockTransport. Nenhuma credencial real ou saldo da conta é necessário.

## Resultados desta entrega

- Backend em memória: **124 passed**, incluindo mundo, eventos, integração e autenticação admin.
- Redis real 7.4 em Docker: **124 passed**.
- Frontend: **16 testes TypeScript**, typecheck, build e fluxo de ponta a ponta no Brave.
- Nenhuma chamada AWS realizada.
- Build da imagem da API aprovado com as dependências de runtime, sem grupo dev.
- O enriquecimento de personas, as rotas de conversa, a reserva Redis e os tokens por perfil estão descritos em [conversa_jogador_persona.md](conversa_jogador_persona.md).

O encerramento do container de teste preserva os serviços e volumes da aplicação. A validação não cobre distribuição estatística do sorteio, reinício do servidor, persistência em disco, carga/contenda prolongada nem comportamento real do modelo.

Referências: [fakeredis](https://fakeredis.readthedocs.io/en/latest/) e [plugin de testes AnyIO](https://anyio.readthedocs.io/en/stable/testing.html).

A validação visual e do build servido, incluindo uma chamada real separada ao Qwen, está descrita em [entrega_visual.md](entrega_visual.md). A suíte comum usa apenas inferência simulada.
