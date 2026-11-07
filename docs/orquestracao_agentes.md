# Orquestração de NPCs e mestre da mesa

O servidor decide fatos, permissões e consequências. Cada NPC tem uma identidade vinculada à partida e consulta somente sua visão autorizada. O LLM seleciona formas de expressão e opções previamente permitidas; não cria encontros, álibis ou provas por texto livre.

## Caminho de uma conversa

1. A API valida partida, interlocutor, posição e disponibilidade. As reservas Redis de conversa e de ação do jogador impedem operações incompatíveis ao mesmo tempo.
2. O `HarnessService`, composto em `src/composition.py`, usa `TableDialogueWorkflow` nas conversas de produção.
3. `GameTableService.prepare` interpreta a consulta e consulta a mesa e o conhecimento autorizado. O ator e o destinatário vêm do servidor.
4. O tom da fala vem de uma escolha local por personagem e é combinado com a resposta canônica. Essa escolha cosmética não faz uma chamada de IA nem mantém o jogador esperando por ela.
5. O mestre da sessão persiste as declarações verificadas e o par de mensagens por um outbox idempotente. A admissibilidade e a força do relato seguem regras de tipo, fonte e cobertura.

Circulação social, assembleia e editoriais continuam tendo seus próprios usos de IA. Separar esses fluxos evita que uma escolha de apresentação atrase uma resposta que a mesa já pode fornecer pelas regras.

## Identidade e acesso

`BoundGameAgent` fixa `(game_id, npc_id)` e permite consultar presenças noturnas, observações próprias e fatos públicos. `PersonaTableAgent` acrescenta relações e conhecimento compartilhável. São agentes lógicos com ferramentas e escopo por personagem, não processos autônomos com acesso irrestrito ao Redis.

O modelo não recebe credenciais, chave Redis ou liberdade para substituir a identidade consultada. Um NPC não acessa o segredo de outro por conhecer seu nome. A consulta aplica as permissões antes de montar a resposta.

## Noites e álibis

A mesa cria `NightRecord`, encontros compartilhados e presenças individuais. As duas pessoas de um encontro apontam para o mesmo registro, local e período. A fera e autores de crimes daquela noite ficam sem companhia; civis também podem passar a noite sozinhos. Não há álibis falsos nesta implementação.

Quando Floriano ouve uma pessoa acompanhada, a declaração aguarda confirmação. Ao ouvir a outra pessoa sobre o mesmo encontro, ambas as declarações passam a confirmadas. Estar sozinho, ter cobertura parcial e não haver informação disponível são estados diferentes. Repetir uma pergunta não cria novas fontes ou pistas duplicadas.

O cenário inicial garante uma observação por um sobrevivente com visibilidade compatível. Ver alguém não equivale a passar a noite com ele nem a testemunhar um ataque. Perguntas sobre noites futuras pedem outra data e não geram prova. Os invariantes são implementados em `src/modules/table/rules.py`.

## Fofocas, segredos e relações

`KnowledgeService` mantém tópicos autorais, relatos recebidos, raízes e fontes em `SocialState`. As permissões `can_share` e `can_confide_personal` limitam o que pode sair da visão de uma persona. Relações influenciam as opções liberadas; ressentimento não concede acesso a fatos privados de terceiros.

O texto livre de Floriano é uma citação atribuída ao jogador com baixa confiança, não um fato novo da mesa. A fala renderizada do NPC também não é reextraída por um LLM para virar conhecimento canônico. A ajuda reconhecida pelas regras, como apresentar um objeto elegível, pode melhorar confiança e afinidade uma vez por NPC por dia; elogios livres não concedem esse efeito.

O `SocialWorker` agenda encontros em janelas de 60, 120, 180 e 240 segundos, com até quatro encontros por dia, reservas e limites de consumo. O fluxo social com LangGraph oferece ao LLM apenas IDs de alegações permitidas e as opções de repetir ou encerrar. O servidor compõe as proposições e preserva a origem ao retransmitir: a mesma fofoca repetida por várias pessoas não vira várias fontes independentes.

## Mestre, delegado e persistência

O mestre coordena a aplicação das declarações e a narrativa das consequências já autorizadas. Ele não pode conceder um álibi porque uma frase parece convincente. O delegado considera as declarações estruturadas selecionadas para o caso, destinadas ao jogador, e suas fontes. Um álibi confirmado vale para a noite coberta; não elimina evidências relativas a outras noites. A interface apresenta os relatos úteis com o tratamento visual roxo e dourado e seu estado de confirmação.

Depois que uma prisão é gravada, o mestre pode preparar o editorial em segundo plano durante o suspense da animação. Ele usa a informação privada que a mesa já possui, sem esperar um sinal do navegador. O texto preparado fica separado da resposta pública e só pode ser aproveitado quando o motor confirmar o resultado e os fatos ainda corresponderem à mesma prisão. Se a geração atrasar, falhar ou for interrompida por um reinício, o jogo publica a edição canônica de fallback e segue sem esperar pelo modelo.

| Estado | Responsabilidade |
| --- | --- |
| `<prefix>:game:{id}:investigation` | Agregado autoritativo, incluindo `table` |
| `<prefix>:game:{id}:table` | Projeção de inspeção gravada na mesma transação |
| `<prefix>:game:{id}:social` | Relações, conhecimentos, proveniência e encontros sociais |
| Memórias, outbox e rastros | Histórico de falas, entrega idempotente e observabilidade |

Investigação e mesa usam formato 2. Registros antigos incompatíveis são recusados; não existe adaptador. O namespace padrão `ml:v1` não é o número do formato de investigação.

## Código e verificação

Os pontos de entrada são `src/modules/table/`, `src/modules/agents/`, `src/modules/knowledge/`, `src/modules/social/` e `src/modules/session_master/`. A composição e os clientes medidos ficam em `src/composition.py`; uso e falhas podem ser acompanhados no admin.

Consulte [testes e simulações](testes.md) para verificar confirmação recíproca, isolamento, proveniência, concorrência e comportamento pela API real. O workflow antigo de diálogo continua coberto por testes específicos; ele não substitui o caminho da mesa na composição de produção.
