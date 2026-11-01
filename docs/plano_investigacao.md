# Plano da investigação e propostas de evolução

O ciclo solicitado está sendo construído nas frentes descritas em [contratos_ciclo_investigacao.md](contratos_ciclo_investigacao.md). O plano foi apresentado durante a execução paralela. A primeira versão implementa o relógio real de cinco minutos, noite sem ação do jogador, jornal pela manhã, vestígios físicos, apresentação de objetos, acusação e prisão com confirmação noturna. Não atribui ao modelo a autoridade de matar, criar provas ou decidir vitória.

## Caminho jogável

Floriano começa diante da banca O Clarim do Rio na Praça Verde. A edição anuncia Brás Cubas e sua cena. O jogador procura vestígios, aborda suspeitos e mostra os objetos. Cada depoimento fica no caderno com autor e objeto; uma lembrança sobre um objeto semelhante não comprova a origem do vestígio. O tempo continua durante conversas. Ao anoitecer, os controles bloqueiam e as regras resolvem a noite. A nova edição e o retorno à banca marcam a manhã seguinte.

Cada personagem possui um objeto exclusivo, um singular compartilhado por poucos e três entre dez tipos comuns. Há vinte tipos no total: sete exclusivos, três singulares e dez comuns. Isso oferece sinais de diferentes precisões. O motor não sorteia uma nova resposta toda vez que o mesmo item é apresentado à mesma pessoa. Testemunhos de quem morreu continuam disponíveis no caderno.

O delegado aceita um conjunto corroborado, não o simples nome do culpado. Ele recebe o mesmo conjunto de fatos observáveis qualquer que seja o sorteio, sem ler o papel do acusado. Prender o lobisomem produz vitória somente na noite em que ele se transforma na cela e é expulso. Uma prisão errada protege o inocente naquela noite, mas não impede outro ataque. O inocente é solto pela manhã. Se morrerem todos os civis, a investigação termina em derrota.

## Propostas para próximas etapas

| Mecânica | Como funcionaria | Efeito na investigação |
| --- | --- | --- |
| Origem dos rumores | Cada alegação aponta observador inicial e cadeia de quem contou a quem | Dois relatos vindos da mesma fonte não contam como corroboração independente |
| Confronto de versões | Apresentar um depoimento registrado e pedir explicação para uma contradição | A mentira passa a ter custo de coerência, sem tratar toda hesitação como prova de assassinato |
| Álibis por local e período | Registrar presenças verificáveis e alegações separadas para manhã e tarde | Cruzar oportunidade com vestígios e relações; um objeto comum sozinho continua ambíguo |
| Exame de um vestígio | Uma ação revela desgaste, material ou parte de inscrição, sem indicar dono automaticamente | Aumenta a precisão de uma pista com custo de tempo |
| Empréstimos e circulação | Itens podem ser emprestados por ações autorizadas e auditadas | Posse e autoria deixam de ser equivalentes; a cadeia material continua verificável |
| Confiança do delegado | Acusações sem sustentação reduzem a disposição de conceder nova prisão por um período | Incentiva esperar por corroboração, sem transformar a decisão em sorteio oculto |
| Pedido de observação | O detetive pede a um civil que observe um local; ele poderá aceitar ou recusar conforme interesses | Produz sinal com custo e origem, mais forte que uma promessa sem ação |
| Correções do jornal | Publicar esclarecimentos quando um relato não se sustenta | A informação pública evolui sem reescrever o histórico original |

Essas propostas não são requisitos implícitos desta primeira entrega. Em particular, encontros NPC–NPC autônomos, empréstimos, fabricação de provas, reputação e custo de exame exigem contratos próprios antes da implementação.

## Critérios de equilíbrio

Informação parcial deve permitir dedução e dúvida. Segredos civis explicam omissões sem implicar licantropia. Uma fala do LLM é discurso; um evento validado é fato. O critério do delegado é público e testável. A identidade só é revelada ao encerrar a partida. Os testes devem demonstrar um caminho de evidências para cada um dos sete sorteios, além de prisão errada, passagem do tempo sem cliente ativo e concorrência entre abas.

O relógio usa UTC do servidor e transações Redis idempotentes. A resolução é feita ao sincronizar ou agir; a passagem do tempo continua válida durante ausência, e a retomada processa as noites já vencidas até o desfecho. Não há ação noturna controlável pelo navegador. Uma inferência que ultrapasse o anoitecer não pode gravar um novo diálogo no dia encerrado.

## Arte e apresentação

A banca recebe identificação textual na interface, mantendo escrita fora dos pixels dos assets. A roda de capoeira do Cais é um atlas transparente com quatro poses, criado por **image_gen built-in**, em `frontend/public/assets/ambient/capoeira.png`, com metadados em `capoeira.json`. Prompts completos, dimensões e origem em [capoeira-prompts.json](../frontend/public/assets/ambient/capoeira-prompts.json). A animação é ambiental, sem papéis secretos, interferência em pistas ou mudança do fundo estático; respeita redução de movimento.
