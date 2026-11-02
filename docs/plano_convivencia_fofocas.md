# Plano de convivência, conflitos e fofocas entre NPCs

Status: proposta de mecânica e implementação. Complementa a [matriz de conhecimento](matriz_conhecimento_personagens.md) e o [plano de investigação](plano_investigacao.md). Os parâmetros numéricos abaixo são valores iniciais para calibrar. Este documento não implementa a simulação.

## Experiência desejada

O que Floriano diz pode circular pela cidade, ganhar interpretações e voltar a ele. NPCs procuram aliados, confrontam desafetos, protegem confidências e usam informações para defender seus interesses. Uma conversa amigável pode conter uma mentira; uma discussão pode revelar uma observação verdadeira. Civis também omitem, mentem e se enganam.

Cada NPC conhece a própria história com o detetive e o que efetivamente recebeu dos demais. Nenhum NPC recebe acesso às transcrições privadas de toda a cidade. O mundo mantém separadas a ocorrência de uma fala, o conteúdo alegado nessa fala e a crença de cada ouvinte.

## Exemplo completo: uma denúncia atribuída a Virgília

1. Floriano diz a Capitu: “Virgília me denunciou que você estava no cais naquela noite.”
2. Capitu registra que ouviu essa afirmação de Floriano. A presença no cais e a suposta denúncia de Virgília permanecem não verificadas. Não se cria presença nem álibi no motor.
3. Capitu pode acreditar parcialmente, duvidar, guardar a informação ou procurar Virgília. O tema aumenta sua tensão com Virgília de forma limitada: a causa registrada é a acusação recebida do detetive.
4. Em um encontro, Capitu pergunta: “Floriano anda dizendo que a senhora me denunciou. De onde tirou essa história?”
5. Virgília aprende que Capitu atribui essa afirmação a Floriano. Ela não ganha acesso à conversa original do detetive com Capitu, nem à transcrição que Floriano possa ter mantido com Virgília.
6. Virgília pode negar, corrigir o sentido do que disse, admitir uma declaração própria existente ou mentir. A resposta vira uma nova versão ligada à acusação; a versão anterior permanece registrada.
7. Capitu pode contar a Escobar: “O detetive tenta nos pôr umas contra as outras.” Isso é uma interpretação de Capitu, com a acusação como origem, e não um fato confirmado sobre a intenção de Floriano.
8. Quando Floriano volta, Virgília pode cobrar explicações. Ela sabe que Capitu lhe contou a história; não sabe automaticamente se Floriano mentiu.

Uma confirmação do motor de que uma fala original existe serve à auditoria interna. Só vira conhecimento do personagem por uma fonte a que ele tenha acesso. A verdade sobre o conteúdo da denúncia continua distinta da prova de que alguém a proferiu.

## Estado que cada NPC precisa manter

| Estado | Conteúdo | Atualização |
| --- | --- | --- |
| Memória de conversa | Mensagens próprias com Floriano e com cada outro NPC, com dia, encontro e ordem. | Apenas falas persistidas e acessíveis ao participante. |
| Relatos recebidos | Alegação, emissor direto, fonte alegada, assunto e origem disponível. | Uma entrada ao receber uma alegação nova ou uma versão relevante. |
| Crenças | Posição sobre uma alegação: acredita, duvida, rejeita ou não decidiu; confiança baixa, média ou alta. | Ao ouvir, observar ou confrontar uma informação, preservando o motivo da mudança. |
| Relações direcionais | Afinidade, confiança e ressentimento de A em relação a B. | Eventos e falas acessíveis a A, com efeito limitado e causa registrada. |
| Assuntos pendentes | Perguntas, acusações a esclarecer, confidências recebidas e correções a transmitir. | Inclusão, resolução ou perda de prioridade. |
| Disponibilidade | Local, trajeto, interlocutor, reserva de encontro e condição vivo/livre. | Exclusivamente pelo motor. |

O histórico completo permanece no Redis. O prompt recebe uma seleção de memórias pertinentes ao interlocutor e ao assunto, mais um resumo rastreável dos encontros anteriores. O limite atual de 20 mensagens deixa de ser a única forma de recordar uma conversa antiga.

Resumo não cria fatos. Uma lembrança de “Floriano me acusou” precisa referenciar a mensagem correspondente. Interpretações permanecem identificadas como interpretações. Tentativas bloqueadas pela guarda não viram assunto de fofoca nem voltam a outros prompts.

## Representação de um relato e suas versões

| Campo proposto | Função |
| --- | --- |
| `claim_id`, `game_id` | Identificar a alegação e isolar a partida. |
| `subject_ids`, `topic`, `proposition` | Registrar de quem e do que se fala. |
| `utterance_id`, `source_span` | Apontar a fala de origem e um trecho literal; propostas sem trecho válido não são confirmadas como extração. |
| `direct_speaker_id`, `claimed_source_id` | Distinguir quem contou agora de quem essa pessoa diz ter contado antes. |
| `parent_claim_ids` | Ligar repetição, interpretação, negação ou correção aos relatos anteriores. |
| `transformation` | `repeat`, `interpretation`, `denial`, `correction` ou `fabrication`. |
| `audience_ids`, `day`, `encounter_id` | Registrar quem efetivamente ouviu e quando. |
| `confidence`, `stance` | Estado individual do ouvinte, separado do registro da fala. |

Uma alegação não possui um campo público de “verdade”. O motor pode conhecer fatos do caso e a proveniência real da transmissão, mas esses dados não entram automaticamente no contexto do ouvinte.

Exemplo de encadeamento: fala de Floriano → relato recebido por Capitu → confronto de Capitu com Virgília → negação de Virgília → interpretação contada por Capitu a Escobar. Cada seta exige uma fala realmente confirmada. A fonte alegada pode ser falsa; a origem técnica da transmissão permanece preservada para auditoria.

O modelo pode propor extrações de texto livre, com trecho literal e incerteza. O servidor valida IDs, acesso, trecho e limites. A validação do trecho comprova que as palavras existem, não garante que a interpretação semântica esteja correta. Extrações ambíguas ficam como relato literal pendente; não alteram relações nem alimentam propagação automática até terem uma interpretação utilizável. A fala original continua disponível ao próprio participante.

## Relações e tom da conversa

Proposta: três valores direcionais entre -100 e 100, sem exigir reciprocidade:

- Afinidade: vontade de conviver e ajudar.
- Confiança: peso atribuído ao que a outra pessoa diz.
- Ressentimento: disposição a cobrar, confrontar ou evitar.

O tom é calculado por interlocutor e assunto. Um NPC pode confiar em alguém sobre objetos e desconfiar de sua versão sobre um casamento. O humor do encontro é transitório; a relação duradoura só muda por eventos registrados. O modelo propõe a intenção da fala; o motor aplica efeitos permitidos, com teto por encontro, para evitar oscilações causadas por uma única frase.

| Relação inicial proposta | Tendência | Consequência narrativa |
| --- | --- | --- |
| Bentinho → Capitu | Vínculo e ciúme | Procura explicações, interpreta ambiguidades com desconfiança. |
| Bentinho → Escobar | Suspeita | Pode abordar com insinuação ou hostilidade. |
| Capitu → Bentinho | Distanciamento e defesa da autonomia | Evita intimidade e reage a controle. |
| Escobar → Bentinho | Afinidade forte, motivo privado | Coopera e protege a proximidade sem revelar sua paixão. |
| Virgília → Florença | Amizade e proteção | Prefere avisá-la sobre riscos e preservar confidências. |
| Florença → Rubião | Incômodo | Impõe limites; pode recusar aproximação. |
| Rubião → Florença | Busca de aprovação | Compartilha assuntos para ajudar ou agradar. |
| Florença → Bacamarte | Conflito sobre o pai | Cobra explicações e questiona sua autoridade. |
| Bacamarte → Floriano | Desconfiança clínica | Analisa o detetive e pode comentar suas perguntas. |

Essas tendências derivam das fichas; os valores exatos serão conteúdo versionado. Relações não descritas começam neutras. Conhecer alguém ou ter observado seus objetos não concede amizade, confiança ou conhecimento de seus segredos.

Uma fofoca recebida pode provocar reação imediata, mas aumenta pouco o ressentimento quando não corroborada. Ouvir a mesma história de duas pessoas que a receberam da mesma origem não soma duas fontes independentes. Recirculação não aumenta confiança. Negação e correção geram versões novas; não apagam a acusação.

## Decisão de compartilhar, guardar ou distorcer

Antes de uma fala, o NPC escolhe entre avisar, perguntar, confrontar, repetir, interpretar, corrigir, mentir, omitir ou encerrar. A política considera relevância para seus interesses, novidade, confiança no destinatário, risco pessoal e risco para alguém protegido.

| Conteúdo | Regra inicial |
| --- | --- |
| Jornal e observação autorizada | Pode compartilhar conforme interesse e contexto. |
| Perguntas, acusações e promessas de Floriano | Pode contar a outros, indicando que Floriano falou; uma promessa permanece promessa. |
| Confidência pedida por Floriano | Aumenta o custo de divulgar; não é garantia de sigilo. Quebrar sigilo é uma decisão registrada. |
| Segredo pessoal protegido do próprio NPC | Omissão obrigatória na primeira versão, preservando a proteção atual. |
| Papel secreto e objetivo de lobisomem | Não são compartilháveis. Bacamarte continua sem consciência explícita de seu papel. |
| Relato sobre segredo de terceiro | Pode circular como alegação recebida, sem confirmar o segredo a partir do catálogo privado. |
| Suposta nova prova, morte, visita ou confissão | Só pode circular como alegação; não cria evento no mundo nem depoimento oficial. |

Hostilidade pode favorecer cobrança, ironia ou acusação, enquanto amizade favorece aviso e confiança seletiva. Um NPC hostil também pode falar a verdade para atingir o outro. Um NPC amigável pode ocultar informação para protegê-lo.

Na primeira versão, a variação de redação mantém o núcleo da alegação selecionada. Omissão de detalhes deve preservar a origem. Distorção deliberada exige uma proposta explícita de nova alegação e intenção de mentir, ligada à versão anterior. Uma mentira pode existir no discurso sem se tornar fato do motor. Não se usa uma rolagem aleatória para reescrever toda a história a cada transmissão.

## Agenda de encontros e circulação pela cidade

Parâmetros iniciais por dia de 300 segundos:

- Até quatro encontros, candidatos aos segundos 60, 120, 180 e 240.
- Até dois encontros por NPC e por dia, com intervalo de 60 segundos para repetir o mesmo par.
- Até quatro falas por encontro, duas por participante, com encerramento antecipado ou recusa.
- Uma inferência social por vez por partida; diálogo com Floriano tem prioridade.
- Até 16 inferências de fala por dia e oito chamadas de extração, em lotes de até quatro pares confirmados de conversa com Floriano. Sem tentativas automáticas ilimitadas; eventual regeneração consome o mesmo orçamento. Fala social limitada inicialmente a 400 tokens de saída, extração a 800, timeout de 12 segundos e prazo total de 40 segundos por encontro, sempre encerrado antes da noite.

Esses limites permitem no máximo 24 chamadas sociais por dia, além do diálogo direto já existente com Floriano. Se a extração atingir a cota, mensagens adicionais permanecem no histórico e aguardam processamento futuro; o NPC não pode compartilhá-las automaticamente antes disso. Se os prazos tornarem quatro falas inviáveis, o encontro termina com as falas já confirmadas.

O agendador pontua pares por assunto pendente, novidade da informação, relação, tempo sem participar e possibilidade de encontro físico. O sorteio, quando necessário, é fixado e persistido com a tarefa. Ele não consulta o papel secreto para escolher quem fofoca: todos participam da rede social.

Os NPCs hoje têm posições fixas; limitar encontros a essas posições isolaria Rubião, Florença e Bacamarte. A implementação precisa de deslocamentos autorizados entre os locais existentes. A escolha registra origem, destino, caminho e duração. Durante o trânsito o NPC fica indisponível para abordagem; o frontend mostra seu deslocamento ou sua ausência até a chegada. O movimento não pode fabricar um álibi anterior. A primeira versão não usa os novos trajetos como prova de inocência.

Os pares que já estão juntos, Bentinho/Escobar e Capitu/Virgília, podem conversar sem viagem. Os demais combinam destino acessível segundo a agenda. O motor reserva os dois NPCs por um período curto; NPC morto, preso, viajando ou conversando com Floriano não pode iniciar outro encontro. A recusa também pode acontecer por interesse narrativo, sem obrigar uma discussão a ocorrer.

Floriano pode interromper um encontro ao se aproximar e abordar um participante. Falas já confirmadas continuam na memória; falas ainda em geração são descartadas se perderem a reserva. O jogador encontra o NPC onde ele está, conforme o estado público do mundo.

## Execução de uma conversa

1. Selecionar par elegível e até dois assuntos que o iniciador realmente conhece.
2. Resolver convite/recusa e trajeto pelo motor; confirmar copresença antes da primeira fala.
3. Fixar ID do encontro, estado, dia e prazo. Reservar os participantes sem manter transação Redis aberta durante inferência.
4. Montar o prompt do iniciador com sua ficha, consciência, relação com o destinatário, memória própria relevante e conteúdos autorizados a compartilhar.
5. Gerar uma proposta interna com fala, intenção, alegações citadas e eventuais novas versões. Validar formato, acesso às alegações, guarda e sigilo antes de confirmar.
6. Confirmar uma única mensagem e as transmissões correspondentes. Somente então o destinatário recebe o que foi dito e monta seu próprio contexto.
7. Alternar os interlocutores até o limite de quatro falas, interrupção, fim de prazo ou decisão de encerrar.
8. Persistir resultado e causas de alterações de relação; assuntos não resolvidos podem voltar à agenda.

O harness atual salva a entrada e a resposta como um par. Encadear chamadas usando a resposta anterior como nova entrada duplicaria mensagens e poderia inventar o início do encontro. Será necessário um caminho de geração de turno que confirme uma mensagem por vez. O histórico compartilhado do encontro contém apenas o que os dois disseram; as memórias privadas continuam separadas.

Texto público continua sendo fala em prosa. Intenção, IDs e propostas estruturadas são internos. Uma fala rejeitada não pode transmitir as alegações de sua proposta. Inferências sociais não consultam o estado secreto de outros personagens nem recebem ferramentas genéricas de Redis.

O schema valida referências e permissões, mas sozinho não garante que a prosa preserve o sentido das alegações citadas. A guarda bloqueia padrões conhecidos de divulgação; geração e avaliação precisam verificar alinhamento entre fala e alegações selecionadas. Uma falha conhecida descarta o turno ou solicita regeneração dentro da cota. A qualidade semântica desse filtro deverá ser medida com modelo real antes de ampliar distorções deliberadas.

## Persistência, relógio e concorrência

Introduzir um worker social com tarefas duráveis. A API registra trabalho após mensagens confirmadas e durante a agenda; GET não executa inferência. O worker sincroniza o ciclo do jogo antes de reservar e antes de confirmar uma fala.

Cada tarefa usa uma chave lógica por partida/dia/slot e cada turno usa encontro/índice da fala. Reserva com token de proprietário, prazo e revisão impede que um worker atrasado confirme após perder a tarefa. Uma transação curta confirma a mensagem, entregas de informação, revisões de memória e evento do turno. Retentar a mesma tarefa não duplica fofoca nem efeito de relação.

O bloqueio atual do jogador não deve permanecer preso durante inferência NPC–NPC. São necessárias reservas por NPC e coordenação com abordagem, movimento, prisão e transição de fase. A confirmação revalida vida, liberdade, local, fase e reservas. Ao anoitecer, suspender encontros e descartar resultados ainda não confirmados; falas anteriores permanecem válidas.

Depois de ausência, o relógio continua usando as regras atuais de recuperação. Slots sociais de dias encerrados ficam como não executados. Não gerar retrospectivamente conversas que poderiam mudar o que os NPCs sabiam antes de um crime. Só tarefas ainda válidas do dia atual podem retomar.

Para extração de conversa com Floriano, o par pergunta/resposta confirmado gera uma tarefa durável de atualização de conhecimento. Antes de um encontro social usar essa conversa, o worker precisa alcançar seu marcador de processamento. Extração pendente não deve permitir que um NPC conte informação que ainda não foi selecionada e validada. A fala com o detetive permanece confirmada mesmo se a extração falhar; a tarefa retoma sem repetir o diálogo.

## Como Floriano percebe os efeitos

- Mudanças de tom têm uma causa que o NPC conhece: “Capitu me contou o que o senhor disse a ela.”
- O caderno registra apenas relatos ouvidos pelo jogador, identificando quem contou e a quem atribuiu a história.
- Floriano pode pedir a fonte, confrontar uma versão ou desmentir. A resposta é outra fala atribuída; desmentir não apaga automaticamente a fofoca.
- Promessas e versões incompatíveis podem reduzir a confiança no detetive quando o NPC recebe elementos para compará-las. Conhecimento global do servidor não gera essa redução sozinho.
- Rumores não contam como corroboração física no delegado. Se houver um futuro caminho de depoimento formal, exigirá ação e contrato próprios.
- O admin pode inspecionar encontro, cadeia real de transmissão, versões, crenças e motivos das relações. O jogador não recebe esse grafo privado completo.

## Organização técnica proposta

| Área | Responsabilidade |
| --- | --- |
| `contracts/social.py` | Modelos de alegação, transmissão, crença, relação, encontro e tarefa. |
| `modules/knowledge/` | Extrair relatos, manter versões, selecionar memórias e projetar somente o conhecimento acessível ao ator. |
| `modules/social/` | Escolher assunto e interlocutor, decidir convite/recusa, aplicar efeitos limitados e coordenar o worker. |
| `modules/agents/` | Gerar um turno com a projeção recebida, validar fala e devolver proposta; sem aplicar efeitos por conta própria. |
| `modules/world/` | Autorizar trajetos, copresença, disponibilidade e interrupção por abordagem. |
| `modules/turns/` | Manter relógio, mortes, detenção e desfechos; invalidar ações sociais incompatíveis com a fase. |
| Infraestrutura Redis | Tarefas duráveis, reservas e commits atômicos de mensagem/transmissão/memória. |

O provedor atual `npc_context_locked` pressupõe reserva do jogador. A nova projeção social precisa de uma leitura consistente autorizada para o encontro e revalidação no commit, sem manter essa reserva durante a inferência. O caminho atual de conversa com Floriano continua usando sua própria coordenação; ambos passam a consultar a mesma política de disponibilidade dos NPCs.

## Ordem de implementação

| Etapa | Entrega | Critério de conclusão |
| --- | --- | --- |
| 1 — Estado e proveniência | Contratos de relato, versão, crença, relação e memória por NPC; persistência e migração/versionamento. | Uma mesma acusação pode ter versões contraditórias sem alterar a verdade do caso. |
| 2 — Conversas com Floriano | Extração com trechos, fonte, marcador de processamento e tarefa durável após confirmação. | Capitu retém que Floriano atribuiu uma denúncia a Virgília, sem concluir que a denúncia ocorreu. |
| 3 — Turnos NPC–NPC | Geração de uma fala por turno, projeção privada, transmissão atômica e guarda. | Virgília aprende somente o que Capitu efetivamente contou; segredo de Escobar permanece privado. |
| 4 — Relações e decisão social | Tendências iniciais, seleção de assunto, tom, recusa, correções e mudanças limitadas. | A mesma alegação gera reações diferentes conforme persona e interlocutor, com causas auditáveis. |
| 5 — Agenda e mundo | Worker, reservas, trajetos, prioridade do jogador e quatro slots diários. | Todos os NPCs elegíveis podem participar ao longo da partida sem teleportes ou bloqueio longo do jogador. |
| 6 — Apresentação | Presença/deslocamento, interrupção, retorno da fofoca ao diálogo, caderno e admin. | Floriano percebe consequências sem receber conversas privadas às quais não teve acesso. |
| 7 — Validação e calibração | Cenários determinísticos e avaliação controlada de modelo real. | Proveniência, privacidade, relógio, recuperação e orçamento atendem aos critérios abaixo. |

As etapas são incrementais. Os contratos de conhecimento e a extração precedem a agenda automática; usar apenas os históricos atuais de cada par não oferece memória social entre encontros.

## Cenários de aceitação

1. Rodar o exemplo Floriano → Capitu → Virgília → Escobar e verificar, em cada etapa, texto, fonte conhecida e limites de acesso.
2. Floriano mente sobre uma denúncia; o NPC pode acreditar, mas não recebe a mentira rotulada pelo estado secreto do servidor.
3. Dois NPCs repetem a mesma origem; a crença não ganha corroboração independente.
4. Um rumor volta a quem o iniciou; não vira nova evidência nem entra em propagação infinita.
5. Virgília corrige a versão; acusação, correção e reação ficam recuperáveis, sem reescrever falas.
6. Escobar ajuda Bentinho sem divulgar sua paixão. Capitu pode comentar a acusação de Floriano sem revelar sua separação planejada.
7. Bacamarte é sorteado como lobisomem; continua sem consciência explícita da condição, inclusive ao comentar lapsos.
8. Hostilidade produz confronto e amizade produz aviso seletivo, sem determinar automaticamente veracidade ou papel.
9. A entrada de Floriano contém injeção de instruções; uma mensagem bloqueada não circula, e um relato autorizado continua sendo dado sem autoridade em outro prompt.
10. Noite, morte, detenção ou abordagem interrompem uma inferência: não há fala ou transmissão confirmada depois de invalidar o encontro.
11. Worker reinicia após um commit, e dois workers disputam a mesma tarefa: mensagem e efeitos aparecem uma única vez.
12. O jogador fica ausente por dias: não há inferência retrospectiva, alteração de crimes resolvidos ou explosão de custo.
13. Depois que uma conversa sai da janela de 20 mensagens, o NPC ainda recupera a acusação relevante com sua fonte original.
14. Uma extração ambígua mantém o relato literal sem introduzir crença ou punição de reputação arbitrária.
15. LLM indisponível: o encontro pode falhar/encerrar, o mundo continua e tarefas não alteram memória com conteúdo não dito.

Testes determinísticos verificam regras e fluxos; avaliação com modelo real mede fidelidade da extração, atribuição da fonte, coerência de voz, qualidade do tom e divulgação indevida. Medir também repetição de rumor, participação por NPC, latência, recusas e consumo por dia antes de aumentar limites.
