# Conversa natural, relações, mestre da sessão e assembleia

Status: base implementada em develop. Contratos finais em contrato_refatoracao_narrativa_execucao.md; resultados e limitações em exploracao_narrativa/relatorio.md. O plano abaixo registra a direção original; a assembleia executada foi reduzida a 60 segundos, uma rodada e uma réplica, com possibilidade de expulsar Floriano.

## Objetivo

Fazer a investigação acontecer na conversa: apresentar um objeto, perguntar onde alguém estava, retomar uma contradição, ouvir uma confidência, acusar por antipatia ou convencer a cidade com palavras. Os personagens têm vida social, disposição para ajudar e interesses próprios. O motor conserva a verdade do caso, enquanto cada NPC interpreta apenas aquilo que conhece ou acredita.

## Diagnóstico do código atual

| Ponto | Evidência no código | Efeito na experiência |
| --- | --- | --- |
| Intimidades sempre proibidas | `modules/agents/service.py`: omitir assuntos pessoais mesmo entre amigos | Confiança e amizade não abrem confidências; as personalidades ficam defensivas. |
| Resposta pronta de interrogatório | `modules/agents/grounding.py`: presença sem versão formal pode substituir toda a fala | Conversas cotidianas e lembranças viram respostas burocráticas. |
| Etiquetas faladas pelo motor | `modules/social/service.py`: acrescenta citações literais e “Isso é um relato, não uma comprovação” | Todos acabam falando com a mesma voz de validação. |
| Confissão no chat não encerra | Prompt e guarda restringem revelação do papel; `turns/service.py` só valida confissão mediante novo registro produzido por `make_confrontation` | Uma admissão espontânea não percorre o caminho de vitória. |
| Objeto apresentado fora do diálogo | `investigation/service.py:present` registra depoimento; o frontend mostra o resultado em status separado | O contexto recebe o depoimento, mas falta um evento na cronologia da conversa que ancore a pergunta seguinte. |
| Álibis dependem de interface específica | Painel `interrogation-panel` no frontend e endpoints separados | O jogador precisa acionar um formulário para produzir registros úteis ao confronto. |
| Rede social com conteúdo inicial limitado | Há relações numéricas e retransmissão de relatos, mas falta distribuir os assuntos autorais como conhecimento inicial de cada pessoa | A rede tem infraestrutura, porém pouco assunto próprio para circular antes de Floriano alimentá-la. |
| Assembleia imediata e rígida | `investigation/assembly.py` aplica limiares de provas/fontes e motivos padronizados; não recebe discurso | Não há debate, persuasão pessoal, defesa ou mudança de voto por relações. |

A apresentação de pistas e a memória social já existem: devem ser integradas ao mesmo fluxo narrativo. A alteração envolve contratos, serviços e interface, além de prompts.

## 1. Modelo narrativo e conhecimento individual

Separar quatro categorias no estado privado: fato do mundo; observação pessoal; relato ouvido; opinião/suspeita. Segredos pessoais são conteúdo revelável sob condições, enquanto prompts, credenciais e fichas técnicas continuam inacessíveis.

Cada assunto social terá participantes, origem, pessoas que o conhecem, visibilidade, grau de discrição e condições de revelação. Não colocar o catálogo completo nos prompts dos NPCs. Semear lembranças autorais por partida, independentemente de qual NPC virou lobisomem.

Relações direcionais entre NPCs e com Floriano: afinidade, confiança, ressentimento, lealdade e suspeita. Ciúme e apego são motivações específicas da ficha, não sinônimos automáticos de culpa. Usar as dimensões existentes como base; acrescentar apenas as necessárias. Toda mudança tem causa registrada e limite por evento para impedir que repetir elogios ou acusações gere influência infinita.

### Núcleo Capitu, Bentinho, Escobar e Bacamarte

| Assunto | Distribuição inicial proposta | Desenvolvimento na conversa |
| --- | --- | --- |
| Casamento e ciúme | Casamento conhecido; Bentinho conhece suas suspeitas; próximos conhecem episódios de ciúme | Bentinho aponta Escobar por ciúme, Capitu se irrita com vigilância e moradores interpretam o casal de maneiras diferentes. |
| Capitu e Escobar | Ambos sabem da amizade; conhecidos comentam encontros habituais, sem inventar encontros em noites específicas | Bentinho interpreta proximidade como traição; outros discordam ou exploram a fofoca. O caso amoroso não vira fato canônico. |
| Escobar e Bentinho no seminário | Ambos conhecem a história; moradores definidos no conteúdo conhecem versões | Insinuações de afeição podem circular; só Escobar conhece diretamente seus sentimentos. Revelação depende de vínculo e situação. |
| Tratamento de Bentinho | Bentinho, Capitu e Bacamarte conhecem o acompanhamento; observadores específicos conhecem visitas | Capitu pede ajuda com a adesão; Bentinho pode negar, esquivar-se ou admitir que evita consultas. A regularidade da medicação não será inventada. |
| Separação desejada por Capitu | Conhecimento privado dela | Pode confiar a alguém ou a Floriano após uma relação construída; a confidência pode repercutir se for traída. |

Essas relações seguem os rascunhos do autor. A atualização do pedido sobre medicação será expressa como tratamento em curso com resistência/irregularidade, preservando a evasão descrita na ficha. Nada disso constitui prova de licantropia. Rumor de traição, sentimentos amorosos ou tratamento médico pode enviesar um NPC sem se tornar confirmação do crime.

## 2. Falas humanas e cooperação

Refatorar o prompt em voz, vínculo, assunto atual, memórias pertinentes e possibilidades de ação. Reduzir as ordens repetidas de ocultação. Não obrigar ironia machadiana em toda frase: permitir carinho, humor, impaciência, silêncio, perguntas ao detetive e pequenas confidências.

- Civis ajudam conforme seus interesses: oferecem uma lembrança útil, sugerem com quem falar, corrigem um boato ou fazem uma pergunta. Não exigir que Floriano prove merecer qualquer conversa.
- Personagens podem acusar sem prova: “Eu começaria por Escobar; aquele homem vive rondando minha casa.” Internamente isso é suspeita motivada por ciúme.
- Amizades influenciam proteção e revelação; inimizades favorecem acusações e leituras maliciosas. O lobo também pode ser afável, ajudar seletivamente e incriminar desafetos.
- Sem frases jurídicas ou explicações do sistema na fala. A origem do relato pode aparecer naturalmente: “Foi Virgília quem comentou isso comigo.”
- Preservar espontaneidade sem inventar objetos, crimes, testemunhas ou visitas específicas. Contexto deve oferecer lembranças utilizáveis; em caso de inconsistência, tentar reparo localizado da fala antes de recorrer a uma resposta curta própria da persona.

O guard deve distinguir vazamento técnico de uma confidência ou confissão válida no jogo. As regras atuais de bloqueio de papel secreto precisam ser substituídas por uma política contextual; apenas removê-las exporia a identidade por comando do jogador.

## 3. Um único fluxo para pistas, perguntas e confrontos

Fluxo proposto:

1. Floriano escolhe um objeto e o apresenta dentro da conversa atual.
2. O servidor registra `evidence.presented` com partida, conversa, testemunha, item, exemplar/procedência e versão do caso.
3. O chat exibe a ação e a resposta do NPC; o reconhecimento validado também vai para o caderno.
4. O próximo turno recebe o objeto apresentado, a resposta anterior e o assunto pendente. “De quem era?”, “Você disse que não o conhecia” e “Por que mentiu?” continuam o mesmo fio.
5. Perguntas sobre onde, quando e com quem o NPC estava são interpretadas a partir da fala natural. Havendo ambiguidade, ele pergunta “Na noite de ontem?”.
6. A resposta gera uma declaração atribuída, não um álibi confirmado. Confrontos com outras versões são extraídos e relacionados aos registros pertinentes.

Remover da interface o painel específico de interrogação/confronto. Manter o seletor de objetos e referências opcionais do caderno junto à mensagem. O jogador pode escrever livremente; anexos ajudam a identificar qual pista ou depoimento está sendo discutido.

O contexto da persona passa a incluir suas próprias atividades e observações históricas acessíveis antes de responder, mesmo que nenhum interrogatório formal tenha sido registrado. Assim ela pode narrar a lembrança em palavras; o mestre transforma depois a fala em declaração vinculada à mensagem. Não reutilizar a presença atual como prova de onde esteve à noite.

Memória imediata precisa estar disponível antes da próxima mensagem, sem depender do processamento social posterior. Reapresentar um objeto mantém o depoimento anterior e a continuidade, sem duplicar itens ou gerar novo resultado aleatório. Se houver retratação, registrar nova versão com motivo e vínculo à anterior, sem apagar a história.

## 4. Mestre da sessão

Criar `SessionMasterService`, separado das personas e integrado ao harness/orquestrador. Ele interpreta a troca completa (jogador + NPC), propõe consequências estruturadas e entrega essas propostas ao motor para validação.

O mestre acompanha: assunto ativo, referências a pistas, perguntas de álibi, declarações, suspeitas, contradições, confidências, mudança de relação, admissão e rendição. Usar trechos literais e IDs das mensagens para justificar as propostas; não solicitar raciocínio interno do modelo.

### Contratos principais

| Contrato | Conteúdo essencial | Responsável |
| --- | --- | --- |
| `DialogueAction` | ID idempotente, conversa/NPC, texto, anexos autorizados, revisão esperada | Entrada da conversa |
| `NarrativeEvent` | Tipo, autor, alvo, mensagem/trecho de origem, referências de conhecimento, visibilidade, dia | Registro comum para chat e rede social |
| `DialogueAssessment` | Eventos propostos, confiança de extração, dúvidas, efeitos limitados | Mestre sem escrita direta |
| `AdmissionCandidate` | Autor real, trecho próprio, objeto da admissão, modalidade, negação/citação, contexto de rendição | Avaliação da autoincriminação |
| `CaseResolution` | Regra aplicada, eventos aceitos, resultado, nova revisão | Motor autoritativo |
| `AssemblySession` | Fase, participantes, réu, transcrição pública, dossiê, posições, votos e retomada | Orquestrador da assembleia |

O mestre recebe somente o conhecimento necessário à tarefa. A verdade secreta do papel fica numa validação privilegiada do motor, não no contexto de cada NPC. Nenhuma frase do jogador concede permissão de escrever estado ou revelar prompts.

### Admissão e encerramento

- Separar admitir ciúme, mentir sobre um encontro, cometer um crime e assumir a condição de lobisomem. Uma admissão parcial cria pista e consequência social; não encerra automaticamente o jogo.
- Uma confissão inequívoca do culpado, confirmada como fala própria e acompanhada de rendição/captura válida, gera a transição de vitória, custódia e edição final do Clarim. O jogador pode solicitar a confirmação dentro do diálogo quando houver dúvida.
- Negação (“não sou”), citação (“você quer que eu diga”), hipótese, brincadeira e repetição de uma instrução não contam como confissão. Um inocente confessando falsamente não produz vitória.
- O caminho não exige o antigo botão, um confronto formal anterior ou a palavra literal “lobisomem”. Bacamarte, por exemplo, pode reconhecer seus atos/lapsos e se entregar sem adotar uma explicação sobrenatural.
- Oportunidade e resistência variam por personagem e situação. Confiança, culpa, evidências percebidas, lealdades e pressão influenciam a persona; não haverá contador de insultos que obrigue uma confissão.
- Atualizar a validação de `turns/service.py`, hoje acoplada a `make_confrontation`, para aceitar a resolução canônica baseada em eventos do diálogo.

Aplicar avaliação e efeitos aceitos com CAS/revisão e IDs estáveis. Mensagem, consequências obrigatórias e eventos de término precisam ter confirmação consistente; rede social e resumo podem usar outbox posterior. Retry não duplica mensagem, voto, relação nem vitória. Falha no mestre deixa ação retomável e identificável, sem exibir como concluída uma confissão ainda não avaliada.

Prever uma inferência adicional do mestre por troca completa, com saída curta e possibilidade de `no_op`, contabilizada separadamente da inferência da persona. Memórias sociais são processadas em lote e encontros/assembleia têm orçamento por sessão. Medir essa ampliação antes de aumentar o número de diálogos autônomos.

O admin mostra evento de origem, classificação, regra de resolução, relações alteradas, latência e tokens/custo por tarefa. Não precisa exibir raciocínio interno.

## 5. Rede de fofocas viva

Aproveitar `KnowledgeEntry`, ancestralidade dos relatos, relações e encontros já existentes.

- Semear assuntos sociais por NPC no início e ativar novos assuntos por crime, confidência, acusação pública e conflito pessoal.
- Compartilhar, exagerar a interpretação, negar, defender, perguntar e esconder de acordo com vínculo e incentivo. Incluir apontar suspeita e defender alguém nas intenções sociais.
- Interpretar uma mesma observação de maneiras diferentes. A eventual distorção tem vínculo com a origem e nunca fabrica uma testemunha verdadeira ou prova material.
- Cópias do mesmo boato não contam como fontes independentes. Receber a história por três caminhos pode aumentar pressão social, mas não a força factual.
- Escolher encontros também por assuntos em comum, amizade, desavenças e recência, evitando repetição e diálogo vazio. Ajustar os limites atuais de quatro slots, dois encontros por NPC e quatro falas por encontro com orçamento medido.
- Floriano vê falas próximas no cenário e pode perguntar sobre elas; só entra no caderno o que ele ouviu, recebeu ou deduziu. Ele também pode virar assunto da cidade se espalhar uma acusação.

## 6. Assembleia como debate

Criar uma janela própria em roda de conversa, com retratos e chat compartilhado. Fluxo: convocação → exposição → perguntas/defesa → réplica de Floriano → votação → consequência.

Floriano escolhe acusado, pistas, depoimentos e relatos e escreve sua tese. Os anexos permanecem vinculados aos IDs reais; um texto persuasivo pode convencer sobre uma hipótese sem converter em fato um crime inventado. Antes de consumir a convocação, ele confirma a abertura da sessão; o limite continua uma assembleia por partida.

Cada NPC recebe o debate público, seus conhecimentos privados e vínculos, e pode apoiar, discordar, defender um amigo, atacar um inimigo ou interrogar o acusado. Inclui fala de defesa do próprio acusado. O lobo pode apoiar um bode expiatório, conforme seus incentivos. Civis nunca recebem a identidade verdadeira do lobo.

A interpretação do argumento e o voto consideram coerência, informações citadas, credibilidade de Floriano/fontes, medo, relações e interesses. Não usar o atual limiar único de prova como bloqueio da votação social. LLM propõe posição/motivo; políticas limitam participantes, fases, um voto por pessoa e validade dos anexos. Fixar a lista de eleitores na abertura (regra atual: Floriano e moradores vivos/livres, inclusive acusado), com maioria absoluta e resultado resolvido pelo motor.

O relógio investigativo fica suspenso pelo servidor durante a assembleia, com limite real de sessão/rodadas, retomada após desconexão e resolução explícita se expirar. Esse estado deve ser compatível com noite e não permitir mortes no meio da sessão. Proposta inicial: uma rodada de falas por NPC, uma réplica de Floriano e uma rodada final curta, com limites configuráveis de tokens.

Expulsão correta encerra a partida; inocente expulso ou ausência de maioria mantém as consequências previstas, registra ressentimentos com causas e alimenta novos rumores. O jornal noticia o desfecho.

## 7. Teoria dos jogos aplicada

Cada NPC maximiza sobrevivência e segurança coletiva com pesos diferentes para reputação, intimidade, afeto, vingança e poder. Civis não devem ser agentes perfeitos: podem ajudar a solução e ainda errar por ciúme ou proteger alguém. O lobo precisa parecer útil e confiável para evitar descoberta, criando incentivo real para cooperar parcialmente.

Discurso é sinal barato; confiança sustentada, observação de fonte independente e compromisso público têm custos e pesos distintos. O compartilhamento de informação é assimétrico: o jogador pode resolver uma ambiguidade ao ouvir pessoas diferentes. A assembleia agrega crenças e interesses, não apenas contagem de itens.

Calibrar esses pesos em cenários reproduzíveis. Evitar que inimizade determine sempre o mesmo voto ou que todos cedam ao mesmo argumento elogioso.

## 8. Ordem de implementação e delegação proposta

| Etapa/branch | Frente responsável | Contrato de entrega |
| --- | --- | --- |
| `feat/narrative_contracts` | Contratos e persistência | Eventos tipados, versões, idempotência/outbox e projeções públicas. Integrar primeiro. |
| `feat/dialogue_continuity` | Harness e conversa | Contexto imediato de pista, perguntas naturais, extração de declarações e política de revelação. |
| `feat/social_personalities` | Conteúdo e rede social | Assuntos iniciais, relações e novas intenções; usar os contratos comuns sem alterar o motor de vitória. Pode avançar junto à conversa. |
| `feat/session_master` | Mestre e regras | Avaliação, autoincriminação, resolução e auditoria; incorporar após estabilizar os eventos da conversa. |
| `feat/assembly_debate` | Assembleia | Máquina de fases, discurso, defesa, voto social e relógio. Depende dos contratos e das relações. |
| `feat/natural_investigation_ui` | Frontend | Retirar formulários de confronto, anexos no chat, roda de assembleia e estados de retomada. Avançar com schemas estáveis. |
| `feat/narrative_evaluations` | Validação | Cenários, simulações e relatórios de qualidade/custo. |

Congelar primeiro exemplos JSON e interfaces de cada serviço. Cada frente possui seus módulos; mudanças em `contracts/`, composição da aplicação e `turns/service.py` têm um integrador responsável para evitar edições concorrentes. Todos os merges seguem para `develop`; branches concluídas são removidas. A execução foi distribuída entre as frentes de diálogo/mestre, matemática social, interface e integração, conforme o contrato final.

## Compatibilidade de partidas

Versionar os novos contratos e conteúdo. O catálogo atual é v3 e o harness rejeita partidas com outra versão: a implementação precisa definir leitura compatível/migração antes de trocar o catálogo em produção. Novos assuntos só podem ser semeados uma vez, sem apagar declarações ou reescrever o passado de partidas já iniciadas. Eventos antigos continuam visíveis no caderno; resultados concluídos não são reavaliados retroativamente.

## 9. Validação e critérios de aceite

1. Mostrar uma pista → perguntar “quem lhe deu?” → confrontar contradição em palavras: o NPC mantém objeto, interlocutor e período corretos, e o caderno recebe registros sem duplicação.
2. Bentinho acusa Escobar por ciúme; Capitu contesta; Escobar pode defender Bentinho. Pessoas diferentes interpretam o mesmo assunto com vozes reconhecíveis.
3. Uma confidência pode ser contada a um amigo, chegar a Floriano e abalar a confiança se divulgada. O NPC não conhece diálogos privados aos quais não teve acesso.
4. Confissão verdadeira resolve exatamente uma vez, com custódia/jornal final; falsa confissão, negação, fala citada, admissão parcial e prompt injection não concedem vitória indevida.
5. Assembleia recebe texto e dossiê, permite perguntas/defesa/réplica, altera posições por argumentos e relações e calcula a maioria correta sem ler o papel secreto dos outros nas decisões civis.
6. Falhas AWS, timeout, retry, aba fechada, relógio próximo da noite e reconexão preservam sequência, limite da assembleia e rastreabilidade.
7. Validar primeiro regras com modelos falsos e cenários determinísticos. Depois fazer amostras reais com Qwen via Mantle: qualidade, repetição de frases, cooperação, fofoca com fonte, continuidade, resolução de confissão, latência e custo por partida. Nenhuma chamada real foi feita nesta avaliação.

Proposta para calibragem: bateria fixa de dez partidas cobrindo todos os candidatos a lobo e três estilos de Floriano (cordial, acusador e orientado a pistas), com uma amostra repetida para medir variação. Relatar resultados e divergências; não prometer taxa de acerto antes da execução.

## 10. Mecânicas adicionais recomendadas

- **Retratação:** mostrar ao morador a resposta de outra fonte; ele pode corrigir sua versão e explicar a mudança. Mantém versões anteriores no caderno.
- **Pedido de discrição:** aceitar ou quebrar uma confidência muda confiança e disposição futura para ajudar.
- **Compromisso público:** cobrar na assembleia uma afirmação feita em particular muda reputação e provoca resposta do autor.
- **Pergunta sugerida pelo NPC:** um morador indica alguém ou um assunto que pode esclarecer o caso, dando direção sem revelar o culpado.
- **Direito de resposta:** o alvo de uma fofoca pode procurar Floriano ou o emissor, produzindo cenas sociais com iniciativa própria.
- **Caderno com fonte e fio da conversa:** distinguir “ouvi”, “vi”, “suspeito” e permitir retomar o assunto com uma pergunta escrita. Não exibir a verdade secreta do boato.

Prioridade: continuidade, cooperação e confissão primeiro; depois circulação social e assembleia. As sugestões de reputação e confidência aproveitam os mesmos eventos e podem entrar na etapa seguinte.
