# Mesa determinística — investigação formato 2

## Autoridade e persistência

`src/contracts/table.py` define NightRecord, NightEncounter, NightPresence, TableObservation, TableStatement e TableState. A investigação tem `version: 2`; o parser recusa registros `version: 1`. Não há migração, reconstrução de partidas antigas ou adaptador.

O agregado `InvestigationState.table` em `<prefix>:game:{UUID}:investigation` é a autoridade transacional de noites e declarações. `<prefix>:game:{UUID}:table` é a projeção materializada do mesmo objeto, gravada na mesma transação de criação/resolução/divulgação. Ela serve à inspeção; nenhuma regra lê uma cópia divergente para decidir fatos. Relações, conhecimentos, origens e encontros sociais continuam em `<prefix>:game:{UUID}:social`. Perguntas/respostas e o outbox existente mantêm seus registros separados e IDs idempotentes.

São sete personas por partida, identificadas por `(game_id, npc_id)`. `BoundGameAgent` consulta álibis, observações próprias e informações públicas. `PersonaTableAgent` consulta conhecimento compartilhável e relações. O servidor fixa ator e destinatário; ferramentas não aceitam identidade substituta e não entregam credenciais ou acesso Redis ao modelo.

## Noites e álibis

Uma noite contém encontros compartilhados e presenças individuais. As duas pessoas do encontro apontam para o mesmo ID, local, período e cobertura. Civis casados Bentinho/Capitu podem formar um par; a regra distribui outros pares e deixa alguns civis sozinhos. A fera e autores de crimes daquela noite não recebem companhia falsa. O cenário inicial garante uma observação breve por um sobrevivente; observador e alvo têm visibilidade no mesmo local. Avistamento não equivale a companhia nem a presenciar um ataque.

Os IDs são derivados de partida/noite/participante e permanecem estáveis em retries. Validações rejeitam companhias unilaterais, autoencontros, fontes trocadas e observações de outra persona. Não há localização falsa, companhia inventada ou lapso arbitrário no interrogatório noturno.

O jogador recebe uma `TableStatement` quando ouve a resposta. A primeira declaração acompanhada fica `awaiting_confirmation`; quando ambas as pessoas declararam o mesmo encontro ao jogador, as duas passam a `confirmed`. Repetir uma pergunta não multiplica registros. `alone`, `partial` e `unavailable` são estados distintos. Uma pergunta sobre noite ainda não resolvida pede outra data e não cria pista.

## Conversa e liberação

`GameTableService.prepare` resolve a consulta e produz o conteúdo canônico. `TableDialogueWorkflow` valida participantes, consulta a mesa, solicita `TableDelivery` e compõe a resposta. Esse DTO contém somente um tom dentre um catálogo finito; não aceita fala factual livre, nomes, fontes, datas ou efeitos. O renderer recebe apenas nome, personalidade e tipos de relato, sem biografia secreta, histórico ou ficha técnica. O prazo de entrega é limitado a cinco segundos (ou um terço do prazo total); falha/saída inválida usa o tom direto e preserva a resposta canônica.

O mestre persiste as declarações internas verificadas e o par de mensagens pelo outbox idempotente. Utilidade/admissibilidade são funções de tipo, fonte e cobertura; a revisão de texto pelo modelo não concede companhia, confiança ou peso de prova.

Fofocas autorais, segredos e relatos recebidos têm raízes e fontes. Uma mensagem livre do jogador fica como citação atribuída; não se transforma em fato ou origem de um segredo. Não se chama um extrator LLM para conceder acesso ou aumentar confiança. A política de revelação consulta o registro e a relação direcionada. Ajuda canônica ao apresentar evidência dá no máximo +5 confiança/+3 afinidade por NPC/dia; repetir a ação no mesmo dia não acumula ganhos. Pedidos, elogios e nomes usados na pergunta não liberam segredos.

Nos encontros sociais, o modelo propõe apenas IDs permitidos com `SocialChoice`. O servidor compõe as proposições e transmite mantendo suas raízes. O destinatário adquire apenas os registros efetivamente compartilhados; circulação da mesma raiz não multiplica fontes.

## Dossiê e interface

`case_reports` é uma projeção tipada de declarações entregues ao jogador. Mostra autor, alvo, noite, companhia, confirmação e admissibilidade. A interface exibe roxo/dourado e distingue confirmação pendente, confirmação obtida e ausência de companhia. O delegado recebe `report_ids` e calcula o peso sem procurar palavras na resposta. IDs privados ou de outra partida são recusados. Um álibi confirmado selecionado é defesa para aquela noite; material de outras noites continua relevante.

## Verificação e execução

Testes cobrem todos os sete papéis, reciprocidade, idempotência, visibilidade, autoria, confirmação, divulgação, cadeia de fontes, desbloqueio por ajuda, indisponibilidade do modelo e seleção do dossiê. Os testes HTTP em `tests/test_table_api.py` usam o mesmo workflow da composição de produção.

O smoke abaixo faz criações, deslocamentos e perguntas por HTTP reais. A API administrativa autenticada é usada apenas como oráculo do avaliador; seus dados nunca entram no modelo. O script não modifica relógio, sorteio, posições ou respostas do provedor e grava um relatório incremental. Configure ADMIN_USERNAME/ADMIN_PASSWORD e use um arquivo de saída novo:

```sh
.venv/bin/python scripts/smoke_table_api.py \
  --api-url http://127.0.0.1:7079 --games 2 \
  --output artifacts/simulations/table-live.json
```

No teste real de 2026-11-06 UTC, duas partidas passaram: 16 mensagens, 14 chamadas concluídas ao Qwen3 32B para entrega, 4.315 tokens de entrada e 352 de saída. Estimativa registrada: US$ 0,00085845. O processamento social foi desativado na instância isolada para a verificação espacial; os testes de política e concorrência cobrem o caminho social. Isso verifica os cenários da mesa, não uma taxa de vitória de partidas completas. Resumo versionado em [relatório](reports/mesa_deterministica_api_20261106.json).
