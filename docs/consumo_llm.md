# Consumo de inferência por partida

O admin autenticado oferece `GET /admin/api/v1/games/{game_id}/usage` e apresenta tokens de entrada/saída, chamadas concluídas/falhas/canceladas, tempo acumulado e custo USD estimado. As tabelas agrupam por finalidade e modelo configurado. Só aparecem contadores e tarifas, sem prompts, credenciais ou textos de resposta.

`MeteredLLMClient` envolve os três clientes da composição: conversa com Floriano, fala NPC–NPC e extração de memórias. `with usage_scope(game_id, purpose, npc_id):` define o contexto antes da chamada. O contexto usa `ContextVar`, com restauração de escopos aninhados e isolamento entre tarefas assíncronas. A resposta é registrada antes de parsers e guardas da aplicação; sua rejeição posterior não apaga consumo pago. Não se executa inferência no endpoint de medição.

Cada chamada tem UUID próprio e registro Redis em hash `prefix:game:{UUID}:llm:usage`. `HSETNX` torna a gravação idempotente. A tarifa é fixada em cada registro: mudar configuração não altera a estimativa histórica. Falhas e cancelamentos sem metadados deixam tokens desconhecidos. Tokens ausentes não são estimados por tamanho do texto. A indisponibilidade da medição é registrada no log e não descarta uma resposta do provedor já recebida; nesse caso o agregado consultável pode estar incompleto.

`known_estimated_cost_usd` é o subtotal dos tokens conhecidos com tarifa aplicável. `cost_complete` só é verdadeiro se todas as chamadas registradas tiverem entrada, saída e tarifa. `coverage=not_recorded` indica ausência de registros, sem alegar custo zero de partidas antigas. Mesmo com `cost_complete=true`, o agregado cobre apenas chamadas registradas: ele não recupera consumo anterior à instrumentação.

## Tarifa

Fonte oficial: [AWS Price List para Bedrock em us-east-1](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.json), publicação `2026-10-30T16:04:56Z`, consultada em 2026-11-01. Os tipos de uso `USE1-qwen.qwen3-32b-mantle-input-tokens-standard` e `USE1-qwen.qwen3-32b-mantle-output-tokens-standard` indicam USD 0,00015 e 0,00060 por mil tokens: respectivamente **USD 0,15 por milhão de entrada e USD 0,60 por milhão de saída**.

Defaults aplicam-se somente a `qwen.qwen3-32b` em `us-east-1`. Outro modelo ou região deixa tarifas desconhecidas até configuração explícita de `LLM_PRICING_MODEL`, `LLM_PRICING_REGION`, `LLM_INPUT_USD_PER_MILLION`, `LLM_OUTPUT_USD_PER_MILLION`, `LLM_PRICING_SOURCE` e `LLM_PRICING_CHECKED_AT`. O custo usa `Decimal`; a interface formata valores pequenos sem arredondá-los a centavos.

É uma estimativa de tabela, antes de créditos promocionais, descontos, impostos e conversão cambial. Não representa a fatura da AWS e não pressupõe gratuidade. Uma falha HTTP ou de parser do adaptador sem metadados confiáveis pode ter consumo desconhecido, mesmo quando a tabela mostra um subtotal de zero.

## Verificação

`tests/test_usage.py` verifica tarifa decimal, snapshot histórico, idempotência, concorrência entre partidas, restauração de contexto, resposta rejeitada após medição, falha/cancelamento, tokens e preços desconhecidos, ausência de registros, corrupção entre partidas e proteção do endpoint por sessão.

Nesta entrega: **12 testes aprovados** com `PYTHONPATH=/tmp:src .venv/bin/python -m pytest -p ml_async_heartbeat tests/test_usage.py -q`; o plugin de heartbeat é o contorno ambiental já documentado para o threadpool deste runtime. Build TypeScript/Vite aprovado com Node 24 local em `/tmp/node-v24.11.0-linux-x64/bin`; mantém o aviso existente de tamanho do bundle Phaser. Nenhuma inferência externa foi usada nesses testes.
