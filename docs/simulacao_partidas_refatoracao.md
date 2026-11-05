# Simulação atual de partidas completas

O único runner mantido é `scripts/run_session_simulations.py`, apoiado em
`src/simulation/`. Ele executa os serviços reais de criação, exploração,
diálogo LangGraph, memória, fofocas, investigação, assembleia e turnos até um
resultado terminal definido pelo motor. A política toma decisões por dados
públicos; a verdade privada é consultada somente na auditoria final.

```sh
uv run python scripts/run_session_simulations.py --games 10 --seed 20261105
uv run pytest tests/test_session_simulations.py -q
```

O modo padrão é **offline**, com provedor simulado declarado. Os mesmos schemas
nativos seguem em `tools`; as respostas passam pelo Runnable LangChain e pelo
`PydanticToolsParser`. Texto contendo JSON não substitui uma chamada de ferramenta.
As falhas injetadas são argumentos inválidos, autenticação recusada e, nos testes,
tentativas de instrução maliciosa. Fallbacks e respostas da guarda não viram
conhecimento narrativo ou provas.

Sem `--redis-url`, o runner usa FakeAsyncRedis. Para Redis real:

```sh
uv run python scripts/run_session_simulations.py --games 10 \
  --redis-url redis://127.0.0.1:16389/0 \
  --output artifacts/simulations/sessions.json
```

Cada execução usa um prefixo exclusivo e remove somente suas próprias chaves.
Não usa FLUSHDB/FLUSHALL, não importa históricos e não migra saves antigos.
O relógio controlado e as políticas exaustivas não representam jogadores humanos.

## Modelo real

```sh
uv run python scripts/run_session_simulations.py --live --games 1 \
  --aws-profile terraform --max-live-calls 100 \
  --output artifacts/simulations/session-live.json
```

O perfil e a cota são obrigatórios. A cota é compartilhada entre personas,
mestre, extrator, convivência, assembleia e editorial, incluindo reparos. O modo
real pode gerar cobrança; esgotar a cota impede a chamada antes do transporte.
Uma partida que prossegue por fallback não comprova sucesso da inferência.

O [relatório nativo](reports/native_sessions_10.json) registra dez partidas
com Redis real e provedor simulado: zero chamadas AWS. A [validação](validacao_saida_nativa.md)
explica seus limites. Tokens offline são estimativas por caracteres; uso e custo
reais do Qwen não foram medidos nessa rodada. O protocolo nativo ainda precisa
ser validado contra o Qwen/Mantle ao vivo após renovar a credencial.

Runners anteriores, seus geradores de relatório e artefatos foram removidos do
checkout. A documentação de decisões do jogo permanece; experimentos antigos
podem ser consultados no histórico Git anterior à limpeza.
