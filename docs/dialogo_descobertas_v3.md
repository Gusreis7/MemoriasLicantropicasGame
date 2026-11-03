# Relatos úteis e descobertas v3

## Causas observadas no código anterior

O prompt repetia mais de uma dúzia de proibições e pressionava por ironia machadiana. Isso competia com a pergunta e com a personalidade. O contexto levava inventários, várias lembranças, relações e biografia sem priorizar o assunto. O reparo do mestre podia redigir livremente outra fala e substituir uma invenção por outra. A confidência exigia proximidade65, enquanto cooperação somava apenas1 confiança por dia; num jogo curto, Floriano quase nunca chegava perto.

## Refatoração

O prompt inicial foi reduzido a uma instrução de voz direta: responder à pergunta, oferecer uma informação autorizada e uma próxima comparação ou pergunta. A persona conserva sua voz/tática ativa, mas o bloco de omissão e pressão não domina cada turno. Humor e opinião continuam possíveis, sem substituir o relato por uma metáfora.

`agents/support.py` seleciona até três apoios por relevância: depoimentos reais, último objeto apresentado, atividades próprias e assuntos sociais compartilháveis. O payload do modelo fica compacto; a lista de fontes conhecidas é preservada separadamente para que uma reação a fofoca não perca a procedência ao reduzir contexto. A pergunta emocional sobre a relação com Floriano pode manter a reação pessoal, sem ser substituída por outro assunto do caso.

Uma fala sem âncora útil recebe apoio contextual na voz da persona. O mestre não escreve mais um novo fato em `corrected_reply`: escolhe `repair_support_id`, e o servidor compõe a informação e o próximo passo a partir daquele apoio autorizado. O caminho não acrescenta uma terceira inferência. Admissões válidas continuam no caminho próprio; o apoio não apaga uma confissão. A checagem de utilidade é uma triagem lexical, não uma prova geral de semântica; resultados reais devem ser avaliados no relatório do coordenador.

## Ritmo de confiança

Uma cooperação explícita e processada ganha confiança5 e afinidade3, limitada à mesma causa por NPC/dia. Insultos e quebras de confiança mantêm seus custos anteriores. Repetir o mesmo elogio no mesmo dia não duplica o ganho.

- Informações públicas não exigem intimidade. Tratamento de Bentinho é compartilhável como acompanhamento/recusa geral, sem inventar dose, horário ou prescrição.
- Capitu e outros: confiança>=10, afinidade>=6, ressentimento<=15, proximidade>=30; alcançável com duas ocasiões/dias de apoio concreto.
- Escobar: confiança>=20, afinidade>=12 e proximidade>=35; exige uma relação mais construída.
- Amigos preexistentes com proximidade>=65 continuam aptos a confidências.

`seeded_topics_version=2` migra só a política dos assuntos autorais existentes; não apaga histórias ou efeitos de relação e não reinicializa resultados. Fonte/visibilidade da informação ouvida continua controlada.

## Conquistas opcionais

`modules/achievements/rules.py` oferece `award(state,id,now,source_message_id=None,source_npc_id=None)`, idempotente. IDs:

- `marriage_triangle`: casamento de Capitu/Bentinho e amizade de Capitu/Escobar, agregáveis entre conversas.
- `seminary_bond`: história de Bentinho e Escobar no seminário.
- `treatment_bentinho`: acompanhamento e resistência ao tratamento de Bentinho.
- `florenca_father`: internação do pai de Florença por Bacamarte.
- `capitu_separation`: confidência afirmativa da própria Capitu com autorização relacional.
- `escobar_affection`: confidência afirmativa do próprio Escobar com autorização relacional.
- `personal_trace`: vestígio pessoal examinado (integração pelo serviço de investigação).

O harness deriva `eligible_discovery_ids` dos assuntos autorizados e `discovery_ids` da fala final ouvida. O mestre não pode conceder conquistas escolhendo IDs. A transição do diálogo confere a fala e persiste a descoberta atomicamente com o evento. Entrada do jogador, pergunta, negação, hipótese, citação e boato não desbloqueiam um segredo privado. Conquistas públicas podem juntar fragmentos legítimos de várias conversas. Cada desbloqueio guarda a mensagem/NPC de origem, sem alterar pontuação de prova ou revelar títulos de segredos ainda desconhecidos.

## Integração

O contrato `Achievement` e `InvestigationState.achievements` são adicionados pelo coordenador. Em `TurnService._validated_confession`, a reconstrução do `ConversationMessage` de saída precisa preservar `narrative_authorized` registrado no evento: uma mesma fala pode confessar e desbloquear uma descoberta.

A apresentação de objeto pode enriquecer o contexto opcional `ultimo_objeto_apresentado` e `seus_depoimentos_registrados.nome`/`item_id`. Nenhuma referência ao dono secreto é enviada como prova automática.

## Correção determinística posterior à auditoria

A correção posterior ao congelamento `9e7ca6f` não integra as métricas das 100 simulações antes/depois. Apoios autorais conhecidos usam a primeira pessoa quando o morador é sujeito; depoimentos e relatos retransmitidos mantêm o texto e a atribuição. O próximo passo aponta a outra fonte ou ao caderno. A descoberta do seminário resolve “eu” pelo emissor de cada mensagem, inclusive na agregação histórica, sem transformar citação, hipótese ou pergunta em fato. “Não toma os remédios” pode afirmar resistência ao tratamento; a negação do próprio acompanhamento continua sem conceder descoberta. As sete conquistas seguem opcionais e sem efeito no peso das provas.
