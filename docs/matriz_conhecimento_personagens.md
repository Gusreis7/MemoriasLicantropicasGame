# Matriz de conhecimento dos personagens

Este documento especifica como separar fatos do mundo, conhecimento individual e relatos. Ele organiza o item 2 do plano de melhoria de memória. Não adiciona fatos canônicos nem altera o comportamento atual do jogo.

## Estado atual e limite desta matriz

O catálogo v3 injeta no diálogo de cada NPC sua própria ficha privada, personalidade, objetivo ativo, estratégia e segredos pessoais que deve preservar. Também injeta o dia/fase, jornal publicado, apetrechos próprios, apetrechos de duas pessoas que o NPC observou e os depoimentos registrados por ele. O histórico da conversa com Floriano também entra no contexto.

O código não mantém um registro geral de crenças por NPC. A matriz abaixo define uma regra de organização para esse conhecimento futuro. Relações e segredos listados como parte da ficha privada são instruções internas da persona; isso não significa que o personagem tenha aprendido tais fatos durante a partida.

Referências de implementação: `modules/characters/catalog.py`, `modules/characters/strategies.py`, `modules/investigation/catalog.py`, `modules/investigation/service.py` e `modules/agents/service.py`.

## Classes de conhecimento

Cada lembrança ou afirmação sobre o mundo deve carregar uma classe epistemológica e sua origem. A classe descreve como o NPC conhece a informação, não se ela é verdadeira.

| Classe | Significado | Exemplo | Regra de uso |
| --- | --- | --- | --- |
| `fato_publicado` | Informação divulgada no jornal do jogo. | A edição noticia uma morte e seu local. | Qualquer NPC pode conhecer após a publicação; preservar edição e dia. |
| `observacao_direta` | O personagem presenciou um evento ou viu alguém usar um objeto. | Viu Virgília com um leque de certo tipo. | Só registrar se o motor ou um encontro autorizado confirmar a observação. |
| `depoimento_proprio` | Declaração que o próprio NPC deu ao apresentar um vestígio. | Disse que já viu pessoa X com objeto semelhante. | Guardar texto e reconhecimento originais; não tratar como verdade do narrador. |
| `relato_recebido` | Afirmação ouvida de outra pessoa, com emissor identificado. | Bentinho disse que suspeita de Escobar. | Guardar quem falou, quando e em que conversa; não converter em observação. |
| `conclusao` | Interpretação do NPC a partir de fatos ou relatos citados. | “Acho que Rubião está ressentido.” | Guardar como crença revisável, com as lembranças que a motivaram. |
| `segredo_proprio` | Intenção, lembrança ou motivação privada da ficha do próprio personagem. | Capitu deseja separar-se; Escobar ama Bentinho. | Disponível somente ao NPC a quem pertence, conforme projeção do papel. |
| `desconhecido` | Informação sem fonte autorizada para este NPC. | Papel secreto, dono real de objeto comum ou conversa alheia. | Não preencher por inferência do sistema ou conveniência do diálogo. |

Uma memória futura deve conter ao menos: `tipo`, `conteudo`, `fonte_id`, `fonte_personagem` quando houver, `dia`, `local` quando houver, `confianca_do_personagem` e `visibilidade`. A confiança é a avaliação do NPC, nunca um campo de verdade do mundo. Fatos autoritativos do motor continuam fora da memória narrativa.

## Conhecimento próprio e segredos

| Personagem | Conteúdo da ficha privada | Segredo ou objetivo sob papel de lobisomem | Limite de projeção |
| --- | --- | --- | --- |
| Bentinho | Ciúme, vigilância de Capitu, receio de expor sua espionagem e evasão dos remédios. | Plano contra Escobar. | Ciúme não confirma adultério nem culpa. |
| Capitu | Trabalho como bruxa por encomenda, clientes, desejo de separar-se e cuidado com a autonomia. | Pode voltar-se contra Floriano se pressionada e perseguir Escobar, conforme a ficha atual. | Clientes e desejo de separação não são evidência criminal. |
| Escobar | Amizade com a família e paixão secreta por Bentinho. | Plano contra Capitu. | A paixão não prova caso com Capitu nem inocência de qualquer pessoa. |
| Rubião | Fortuna, interesse não correspondido por Florença e desejo de aprovação. | Plano contra Virgília. | Devoção não significa reciprocidade; a suspeita sobre Virgília é crença. |
| Virgília | Amizade com Florença, fofocas e consultas com Capitu. | Plano contra Rubião. | Rumor deve conservar emissor e cadeia de transmissão. |
| Florença | Trabalho, pai internado na Casa Verde e defesa de autonomia e direitos das mulheres. | Plano contra Bacamarte. | Crítica a Bacamarte não prova autoria de crime. |
| Dr. Bacamarte | Autoridade científica e interesse em investigar Floriano. | Na ficha, mata ao acaso e nega a condição. | Em negação, não recebe o papel real nem seu objetivo secreto; recebe a projeção de lapsos e medo de enlouquecer. |

Biografia e personalidade são incluídas para todos. O harness seleciona um objetivo ativo conforme o papel: civil recebe o objetivo civil; lobisomem consciente recebe o objetivo de lobisomem; Bacamarte em negação recebe o objetivo civil e a projeção de lapsos. Portanto, a tabela descreve conteúdo de personagem, não afirma que todo objetivo aparece em todo prompt.

O papel dos demais personagens é `desconhecido` para cada NPC. O objetivo de lobisomem dos demais também é desconhecido. Um NPC pode suspeitar de alguém por fatos ou relatos, mas suspeita não revela o papel real.

## Matriz de observações de apetrechos atual

O jogo define apetrechos privados e pares de pessoas cujos tipos de objeto cada NPC já observou. A relação atual vem de dois vizinhos na ordem fixa de `INVENTORIES`; ela é uma regra de cenário do código, não uma observação simulada por local ou horário.

| NPC observador | Pessoas cujos apetrechos observou | O que essa observação permite dizer |
| --- | --- | --- |
| Bentinho | Capitu, Escobar | Já viu essas pessoas usar objetos dos tipos listados. |
| Capitu | Escobar, Rubião | Já viu essas pessoas usar objetos dos tipos listados. |
| Escobar | Rubião, Virgília | Já viu essas pessoas usar objetos dos tipos listados. |
| Rubião | Virgília, Florença | Já viu essas pessoas usar objetos dos tipos listados. |
| Virgília | Florença, Bacamarte | Já viu essas pessoas usar objetos dos tipos listados. |
| Florença | Bacamarte, Bentinho | Já viu essas pessoas usar objetos dos tipos listados. |
| Dr. Bacamarte | Bentinho, Capitu | Já viu essas pessoas usar objetos dos tipos listados. |

O tipo do objeto não prova quem deixou um vestígio. O motor preserva níveis de reconhecimento: objetos comuns podem ser compartilhados por muitas pessoas; objetos singulares são pouco comuns, mas não exclusivos; um objeto exclusivo é sinal mais forte. Até o objeto exclusivo não autoriza o NPC a inventar quando, onde ou como ele foi deixado.

## Contexto por NPC: o que pode entrar na memória

| NPC | Relatos que podem orientar suas crenças | Restrições específicas |
| --- | --- | --- |
| Bentinho | O que Floriano lhe perguntou; declarações recebidas de outros NPCs; notícias publicadas; suas próprias observações autorizadas. | Registrar ciúme e suspeita como crença própria, nunca como fato sobre Capitu ou Escobar. |
| Capitu | Perguntas de Floriano, notícias, observações autorizadas e depoimentos que ela própria prestou. | Proteger informações de clientes; não atribuir culpa por profissão, origem ou desejo de separação. |
| Escobar | Falas recebidas, notícias e observações autorizadas sobre a família e os objetos. | Não usar a intimidade com Bentinho como prova ou álibi; manter a paixão como segredo próprio. |
| Rubião | Falas e limites comunicados por Florença, relatos sobre Virgília e notícias. | Preservar a diferença entre esperança romântica, declaração alheia e observação. |
| Virgília | Relatos com emissor identificado, conversas próprias, notícias e observações autorizadas. | Não apagar a cadeia de rumor; proteger confidências de Florença. |
| Florença | Conversas próprias, notícias e observações autorizadas sobre o pai e a Casa Verde. | Separar abuso de poder percebido, discordância política e evidência criminal. |
| Dr. Bacamarte | Conversas próprias, notícias, observações autorizadas e registros sobre suas próprias lacunas percebidas. | Se estiver em negação, não pode formar memória explícita de “sou o lobisomem”; a projeção deve permanecer compatível com a consciência negadora. |

## Regras para alimentar uma memória futura

1. O motor cria observações de mundo e eventos públicos; o modelo não os cria.
2. Uma fala do jogador ou de outro NPC entra como `relato_recebido`, citando o emissor, mesmo quando parece plausível.
3. Uma fala do próprio NPC entra como `depoimento_proprio`; sua versão original não é reescrita por resumos.
4. Uma conclusão deve citar as lembranças usadas e pode mudar quando chegam novas informações. A lembrança anterior permanece no histórico.
5. Um resumo de conversa comprime a transcrição, mas não altera classe, origem, dia, pessoa citada ou grau de certeza.
6. Informação sobre outro NPC só fica acessível se vier da ficha privada do próprio personagem, de observação autorizada, de notícia pública ou de um relato efetivamente recebido.
7. Morte não apaga lembranças já formadas; morte também não concede acesso retroativo a eventos não observados.
8. A memória narrativa não decide busca, posse, prisão, morte ou vitória. Essas ações continuam sob autoridade dos módulos de regras.

## Lacunas que ainda exigem decisão de cânone

- Quais personagens conhecem previamente os segredos uns dos outros, antes do primeiro encontro com Floriano.
- Se rumores podem circular entre NPCs nesta versão e quais encontros ou fontes os transmitem.
- Quais eventos cada personagem presencia por local e período; a tabela de observação de objetos atual não representa presença física.
- O que Capitu faz como lobisomem além do texto atual, que combina uma reação ao detetive com um alvo.
- Como a intenção de cada lobisomem se relaciona ao crime inicial de Brás Cubas.

Até essas decisões serem tomadas, a memória deve registrar ausência de fonte como desconhecimento, sem completar a lacuna com conhecimento onisciente.

A proposta de encontros, circulação de relatos e consequências nas relações está detalhada no [plano de convivência e fofocas](plano_convivencia_fofocas.md).
