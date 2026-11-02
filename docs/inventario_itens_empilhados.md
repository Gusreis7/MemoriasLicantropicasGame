# Inventário de itens empilhados

## Plano executado

- Usar `item_id` como identidade única do objeto exibido ao jogador.
- Manter a quantidade e a lista das ocorrências físicas no caderno; não repetir o objeto em seletores.
- Usar a primeira evidência recolhida daquele `item_id` como identificador estável para apresentação, confronto, acusação e assembleia.
- Permitir que um depoimento sobre qualquer cópia recolhida daquele mesmo `item_id` acompanhe a única opção selecionada.
- Pontuar cada tipo de item no máximo uma vez, preservando UUIDs de evidências e depoimentos para auditoria e histórico.

## Contratos

- A UI agrupa evidências por `item_id`, exibe a pilha como `Nome × quantidade` e envia um único UUID representativo por tipo.
- `evidence_id` continua identificando a ocorrência recolhida. `item_id` identifica o tipo que o jogador seleciona.
- O serviço só aceita depoimentos de item types selecionados na acusação/confronto/assembleia, mesmo que o depoimento tenha sido registrado sobre outra cópia desse tipo.
- O serviço de apresentação trata novo exemplar do mesmo tipo para o mesmo morador como repetição do depoimento existente.
