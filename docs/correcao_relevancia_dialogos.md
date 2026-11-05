# Relevância e voz nos diálogos

As conversas de 04/11/2026 mostraram saudações e perguntas sobre crenças substituídas por fatos familiares e depoimentos sobre objetos. O problema estava na composição do servidor: quase toda pergunta era classificada como pedido de orientação, apoios sem relação eram elegíveis e o mestre substituía inclusive problemas de estilo por um fato com abertura e encaminhamento fixos.

O harness agora orienta a responder à mensagem atual. Saudação, dúvida e opinião não exigem uma pista. Pedidos de orientação são reconhecidos explicitamente; perguntas específicas recebem apoios ligados ao assunto e à pessoa mencionada. Apresentações de objetos feitas pelo jogador não viram apoios para serem recitadas como descobertas. A composição de emergência não acrescenta aberturas fixas nem encaminhamentos fora de pedidos de orientação.

O mestre continua verificando fatos inventados, confidências indevidas, narração externa e tratamento incorreto do detetive, e identifica respostas fora do assunto. Problemas de estilo, tratamento ou assunto retornam ao próprio NPC para uma única nova geração com a pergunta e o histórico originais. A nova fala é avaliada novamente. Se não houver reparo seguro, nenhum par de mensagens é persistido. A tentativa compartilha o prazo total já existente do diálogo; pode consumir uma geração e uma avaliação adicionais.

Memórias sociais próprias e encontros recentes permanecem no contexto para explicar sentimentos e reações, mesmo quando não constituem uma pista para a pergunta atual. As transcrições existentes são preservadas; somente a moldura automática das falas legadas é retirada da cópia enviada ao modelo. O nome do próprio NPC usado como vocativo não conta como correspondência de assunto.

Validação local: 691 testes aprovados, incluindo as cinco perguntas fornecidas, seleção de assuntos, preservação de proveniência, segredos e regeneração de estilo. As simulações reais foram autorizadas pelo usuário e revelaram falsos positivos do mestre sobre tratamento e narração, inclusive listas com campos redundantes. O parser conserva os problemas tipados mesmo quando há flags extras. Cortesias que pertencem a um vocabulário fechado, sem fatos, segredos ou confissões, dispensam avaliação do modelo; esse caminho não gera frases prontas.

O script de reprodução faz requisições reais e tem custo Bedrock:

```sh
docker compose -f compose.yaml -f compose.aws-local.yaml exec -T api \
  python - --live --rounds 2 < scripts/check_dialogue_relevance.py
```

São duas rodadas das cinco perguntas, com histórico de apresentação do lenço e, na segunda rodada, falas mecânicas antigas. Cada rodada usa prefixo Redis aleatório, removido ao terminar; não consulta partidas existentes. A saída JSON registra falas, avaliações e avisos. Os avisos cobrem o padrão original de repetição e desvio de assunto; não substituem revisão humana de coerência e de fatos inventados. A geração e a avaliação semântica continuam sujeitas à variação do modelo.

Na rodada final com Qwen3-32B, as dez interações retornaram respostas sem erro e sem os avisos acima. Rubião respondeu à pergunta sobre lobisomens com “Acredito, sim. Afinal, quem duvida das histórias que vêm das ruas e das sombras? É melhor tomar cuidado.” e, na partida com histórico legado, “Acho que tais histórias são apenas contos para assustar as crianças. Não vejo motivo para crer nisso.” São partidas distintas, sem exigência de crença idêntica. As apresentações do lenço não substituíram essas respostas.

Capitu manteve o assunto Brás Cubas, sem introduzir o tratamento de Bentinho. Ainda houve elaboração genérica sobre a vida pública de Brás Cubas sem apoio explícito, que o mestre não marcou. Portanto o resultado comprova a correção dos encaminhamentos automáticos observados, mas não garante que toda elaboração factual do modelo esteja fundamentada. As rodadas intermediárias falharam e orientaram as correções; o resultado de dez respostas refere-se à versão final. A API foi reconstruída e aplicada, preservando Redis e transcrições existentes.
