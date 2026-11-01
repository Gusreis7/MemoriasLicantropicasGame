# Contrato de falas e proteção do diálogo

O adaptador Mantle valida o protocolo Chat Completions (uma resposta concluída,
texto não vazio e nenhuma chamada de ferramenta). O harness valida a fala antes
de salvar o par de mensagens no Redis. O corpo de uma resposta do provedor nunca
é tratado como comando, função ou alteração do estado da partida.

## Entrada e saída entre os componentes

| Componente | Entrada | Saída e responsabilidade |
| --- | --- | --- |
| Guarda de entrada | Texto do interlocutor | `GuardDecision(allowed, reply, reason)`; uma recusa dispensa a inferência |
| Harness | NPC e conversa validados, projeção privada individual e histórico permitido | Um prompt de sistema; dados do interlocutor em envelope `remetente`/`fala`; histórico do próprio NPC em texto simples |
| Mantle | Tupla de `ChatMessage` | `LLMResponse`; sem tools, retries ou efeitos no mundo |
| Parser de fala | `content` do provedor e ID do NPC esperado | `str` contendo apenas a fala pública; saída ambígua gera erro genérico |
| Guarda de saída | Fala normalizada e marcadores privados do NPC atual | Liberação ou recusa diegética; texto rejeitado não é persistido nem retornado |
| Memória e API | Pergunta e fala já validadas | Par atômico no Redis; `message.content` em texto simples |

O contrato preferido de saída do modelo é uma fala breve em texto simples. O
parser aceita também o envelope legado **exato**
`{"remetente":"capitu","fala":"O que deseja saber, detetive?"}`, incluindo
um bloco Markdown JSON que contenha somente esse objeto. O remetente precisa
coincidir com o NPC escolhido pelo servidor. A API e a memória recebem apenas
`O que deseja saber, detetive?`.

O parser rejeita IDs divergentes, chaves extras ou repetidas, objetos/listas no
campo `fala`, JSON truncado, envelopes misturados com prosa, ferramentas e tags
de raciocínio. Não tenta consertar ou executar estruturas. Uma falha de formato
gera HTTP 503 pelo tratamento existente e não salva um turno parcial. A mensagem
de erro não contém o conteúdo rejeitado. Não há segunda inferência automática.

## Integração da guarda

`HarnessService(..., history_limit=20, guard=None)` usa `DialogueGuard` por
padrão. Autorização, versão do conteúdo, existência do NPC e participantes são
validados antes da política de diálogo. Uma tentativa bloqueada recebe uma
resposta breve dentro do universo do jogo, com metadados internos
`model="dialogue-guard"` e contagens de tokens ausentes. A API pública mantém o
mesmo schema, sem expor a categoria do detector nem instruções privadas.

O texto da pergunta bloqueada pode permanecer no histórico como fala do jogador,
mas não é reenviado ao modelo em turnos futuros. A guarda de saída recebe apenas
os objetivos e a estratégia ativos da projeção individual; biografias públicas,
o elenco de papéis e os segredos de outros NPCs não são repassados à guarda.
Uma saída que reproduza marcadores confidenciais é substituída pela recusa antes
de chegar ao Redis ou ao cliente.

## Compatibilidade com conversas existentes

O histórico público normaliza envelopes antigos na leitura e aplica a guarda
com os mesmos marcadores privados do NPC. Saídas antigas inválidas ou com
metadados privados são exibidas como uma recusa segura. A consulta não altera os
registros originais. O contexto da próxima inferência também normaliza respostas
antigas e apresenta o histórico `assistant` em prosa, evitando ensinar o modelo
a repetir o envelope de entrada.

As verificações determinísticas reduzem ataques conhecidos e ecos literais; não
são uma prova de detecção de toda intenção maliciosa ou vazamento semântico. A
proteção estrutural continua sendo a projeção individual do contexto, a ausência
de ferramentas e as regras de autorização dos serviços. Nenhuma fala altera
funções, sorteio, credenciais ou estado do mundo.

## Validação

`tests/test_dialogue_output.py` cobre a regressão do envelope observado na UI,
formatos inválidos, identidade divergente, atomicidade da troca, ausência de
inferência em recusas, histórico legado e bloqueio de eco do objetivo privado.
Os testes usam o LLM stub e Redis isolado, sem AWS.
