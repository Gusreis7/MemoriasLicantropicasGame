# Apetrechos, vestígios e custódia noturna

Implementação em `feat/pistas_delegado`, módulo `investigation`. Segue os contratos de [contratos_ciclo_investigacao.md](contratos_ciclo_investigacao.md); o motor de fases e a transação Redis pertencem ao módulo `turns`.

## Catálogo e geração

Cada um dos sete personagens tem cinco tipos de apetrecho: um exclusivo, um singular e três comuns. Há sete exclusivos, três singulares e dez comuns. Exclusivos têm um dono; singulares e comuns são compartilhados por duas ou três pessoas. A propriedade fica no catálogo Python privado e não é serializada para o jogador.

| Personagem | Exclusivo | Singular | Comuns |
| --- | --- | --- | --- |
| Bentinho | Chave com medalhão Santiago | Luvas de couro | Lenço, botão, pena |
| Capitu | Estojo de cartas com olho de cobre | Fita de veludo vinho | Lenço, linha, cera |
| Escobar | Prendedor de gravata em âncora | Luvas de couro | Botão, cordel, moeda |
| Rubião | Relógio com gravação Quincas | Caderneta verde | Fósforos, papel, retalho |
| Virgília | Leque com monograma VN | Fita de veludo vinho | Linha, papel, pena |
| Florença | Broche de andorinha | Fita de veludo vinho | Cordel, fósforos, moeda |
| Bacamarte | Lente de armação hexagonal | Caderneta verde | Cera, retalho, lenço |

Os detalhes são complementos de investigação coerentes com as fichas existentes; não mudam personalidade, relações ou objetivos. São tipos de objeto, não uma simulação de consumo de unidades de inventário. Cada cena contém dois vestígios originados no assassino real: um comum e um singular; a partir da terceira noite o segundo é exclusivo. O crime inicial de Brás Cubas usa o mesmo sorteio, sem colocá-lo no elenco vivo.

O motor escolhe vítimas civis vivas, exclui o preso e prioriza os alvos documentados de cada personagem. Bacamarte, ou um assassino cujo alvo preferido não é elegível, usa sorteio entre as alternativas restantes. Capitu persegue Escobar nesta versão; ataques diretos ao detetive exigem uma regra futura própria.

## Encontrar e apresentar

A busca exige mesma localização e distância de até90px da cena. Cada comando recolhe o próximo vestígio não encontrado; repetir após esgotar a cena não cria objetos, eventos ou revisões extras. O público vê somente quantidade restante antes da busca. Dono real e culpado nunca são campos de uma pista pública.

Apresentação exige NPC vivo, livre e a até64px. O par pista/testemunha é estável: novas apresentações recuperam o mesmo depoimento. O jogador não pode rerrolar uma resposta. Reconhecimento, negação e desconhecimento são fatos estruturados do motor; o texto narrativo do modelo não pode sobrescrevê-los.

Cada NPC conhece seus próprios cinco objetos e já observou os objetos de dois outros moradores, conforme uma matriz estável de conhecimento. Esse acréscimo foi acordado entre as frentes para manter um caminho de dedução: se apenas o dono conhecesse os comuns e ele sempre negasse, seria impossível ligar duas peças ao lobisomem. Uma observação de objeto comum declara expressamente que não prova a procedência daquele vestígio. O lobisomem pode negar reconhecer sua posse; o público não recebe a veracidade privada dessa fala.

`npc_context_locked(game_id, npc_id)` projeta somente seus apetrechos, duas listas de posses observadas, notícias públicas e seus depoimentos anteriores. Reutiliza a reserva já mantida pelo harness; não retorna o inventário global, o culpado ou os papéis de outros NPCs. O jogo pode usar o LLM para dar voz a essas informações autorizadas. A apresentação em si não exige inferência: mantém reconhecimento e evidência verificáveis sem permitir pistas inventadas.

Depoimentos permanecem no caderno quando uma testemunha morre. Os testes verificam um caminho inicial de identificação para todos os sete sorteios com observadores vivos. Mortes sucessivas podem reduzir novas fontes disponíveis; registrar depoimentos cedo tem valor. Como evolução, um livro de registros materiais da cidade pode oferecer uma fonte alternativa limitada caso todos os observadores relevantes morram. Essa fonte ainda não faz parte desta versão.

## Decisão do delegado

Uma tentativa por dia, aceita ou recusada. O jogador apresenta IDs de objetos recolhidos e depoimentos registrados; o serviço rejeita IDs de outra partida, depoimentos sem seu respectivo objeto, pessoa morta ou uma segunda detenção. Texto livre, afirmações do modelo e campos fornecidos pelo cliente não contam como prova.

O avaliador não recebe `GameState` nem consulta a origem privada ou a veracidade do depoimento. Considera somente peças que os depoimentos selecionados ligam ao acusado. Exige dois tipos diferentes e pontuação mínima4: exclusivo3, singular2, comum1, mais1 por identificação registrada. Duplicar IDs, depoimentos ou peças do mesmo tipo não aumenta a pontuação. Dois comuns somam apenas3 com a identificação e não bastam.

Uma decisão aceita justifica apenas a custódia noturna; não anuncia culpa. Um conjunto de relatos enganoso pode levar um inocente à cela. O módulo `turns` decide a transformação, vitória, soltura ou nova vítima na noite seguinte, sem inferência. Os testes alteram origem privada e veracidade sem mudar a decisão do delegado, demonstrando que ele não atua como um oráculo.

## Projeção e API

O router fornece GET `investigation`, POST `crime-scenes/{crime_id}/search` com `{}`, POST `evidence/{id}/present` com `{npc_id}` e POST `accusations` com `{suspect_id,evidence_ids,testimony_ids}` sob `/api/v1/games/{game_id}`. Todas retornam `CasePublic`.

Durante a investigação, `ending` é nulo. Somente no desfecho contém resultado, mensagem e identidade do lobisomem. `CrimePublic` não inclui evidências ainda ocultas nem culpado; `EvidencePublic` omite quem a depositou; `TestimonyPublic` omite veracidade. Campos adicionais de verdade, aceitação, papel ou resultado fornecidos pelo cliente geram422.

## Validação

`tests/test_investigation.py` cobre catálogo, preferências de vítima, pistas por noite, ocultação de dados, alcance e elegibilidade, busca e apresentação idempotentes, negação e desconhecimento, conhecimento autorizado do harness, critérios cegos ao papel, rejeição de inflação, limite diário, testemunha morta, solvabilidade dos sete sorteios e transições reais através do TurnService e Redis. Não chama AWS.
