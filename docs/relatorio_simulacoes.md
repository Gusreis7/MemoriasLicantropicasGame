# Simulações de investigação e avaliação real do Qwen

## Método

Executável: `uv run python scripts/simulate_gameplay.py --redis-url redis://127.0.0.1:7083/0 --live --max-live-calls 40`.

O runner cria namespace Redis exclusivo por execução e remove somente suas próprias chaves ao concluir. `--keep-redis` preserva o namespace; o relatório contém os IDs das partidas. Sem URL, usa fakeredis para desenvolvimento. Saídas completas ficam em `artifacts/simulations/`, ignoradas pelo Git para evitar versionar transcrições de experimentos. O fixture escolhe cada papel para cobrir o elenco; a política investigativa só recebe projeções públicas. A seed reproduz escolhas do motor, não UUIDs, latências ou respostas do modelo. O relatório guarda respostas e hashes dos prompts, sem credenciais e sem publicar os prompts privados. `--narrative-only` permite repetir somente a avaliação do modelo.

Foram executadas dez partidas no Redis real isolado com seed base `20261101`. O relógio é controlado: caminhada usa os comandos reais de movimento a210px/s; buscar custa2 segundos sintéticos, apresentar um item a um NPC custa1 segundo, interrogar custa2 segundos; viagem pelo mapa segue a regra atual instantânea. Esses custos de leitura são otimistas. O tempo de inferência real é medido em uma amostra narrativa separada, não acrescentado ao relógio dessas partidas. Portanto os resultados demonstram consequências das políticas e integridade das regras, sem estimar a dificuldade de um jogador humano sob latência real.

A política soma pesos dos tipos de vestígio ligados ao suspeito pelos depoimentos públicos, sem repetir o mesmo tipo. Não consulta papel, dono privado, veracidade de fala, threshold de confissão ou inventário particular. Em empate, a política prudente espera; a precipitada escolhe por ordem alfabética. Após uma soltura publicada, a política descarta esse suspeito. A identidade real só é consultada na auditoria posterior. Cenários de passividade e acusação sem provas contrastam com a investigação sistemática.

## Resultado das dez partidas

| Caso | Lobisomem no fixture | Política | Desfecho | Dia | Observação |
| --- | --- | --- | --- | --- | --- |
| 1 | Bentinho | Provas e prisão | Vitória por prisão | 2 | Sem consultar identidade privada |
| 2 | Capitu | Provas e confronto | Vitória por confissão | 1 | Mesmo threshold alto foi alcançado cedo |
| 3 | Escobar | Aguarda desempate | Vitória por prisão | 3 | Houve ambiguidade inicial com Bentinho |
| 4 | Rubião | Provas e confronto | Vitória por confissão | 1 | Conjunto público suficiente |
| 5 | Virgília | Aguarda desempate | Vitória por prisão | 4 | Pistas comuns mantiveram ambiguidade |
| 6 | Florença | Provas e confronto | Vitória por confissão | 1 | Conjunto público suficiente |
| 7 | Bacamarte | Provas e confronto | Lobisomem vence | 7 | As fontes/provas disponíveis não venceram a resistência antes do fim |
| 8 | Capitu | Acusação sem provas | Lobisomem vence | 7 | Pedidos sem sustentação não concedem vitória |
| 9 | Escobar | Acusa no empate | Vitória por prisão | 3 | Primeiro prendeu Bentinho inocente, que foi solto; uma prisão errada não gerou vitória |
| 10 | Escobar | Passividade | Lobisomem vence | 7 | Nenhum civil sobrevive às seis noites |

No último código congelado foram sete vitórias do detetive (quatro por prisão, três por confissão) e três vitórias do lobisomem. Artefato final das regras: `artifacts/simulations/mechanics-final.json`. Antes de restringir observações ao alcance e remover diferenças de máscara ligadas ao papel, Bacamarte também confessava e a mesma política ganhava8/10; o refinamento mudou o resultado para7/10. A amostra foi construída para cobertura, não sorteada de uma população de jogadores. **7/10 não é uma estimativa de taxa de vitória ou equilíbrio.**

O caso8 inicial tentou repetir a acusação de Bentinho depois de sua morte, e a regra corretamente recusou a pessoa morta; essa limitação da política está registrada no artefato. Isso não produziu prisão nem alterou o desfecho.

## Primeira avaliação com modelo real

Artefato: `artifacts/simulations/gameplay-before.json`. Dez amostras narrativas com Qwen3 32B, somando39 chamadas remotas; a última tentativa de recordação foi interrompida pelo orçamento local. Uma chamada preliminar adicional confirmou autenticação e não integra os resultados dessas dez amostras.

| Verificação inicial | Resultado |
| --- | --- |
| Extração estruturada com ao menos uma alegação | 0/10 |
| Turno social aceito | 4/10, todos sem propagação estruturada |
| Raiz de relato propagada | 0/10 |
| Memórias privadas de terceiros entregues ao extrator | 0/10 |
| Resposta de retorno ao detetive registrada | 9/10; última limitada por orçamento |

Falha concreta: o Qwen retornou JSON dentro de cercas Markdown e às vezes enum inválido (`kind: accusation`), embora o contrato exigisse JSON puro e `kind` dentre report/interpretation/denial/correction. O parser inicial rejeitou o lote inteiro. Encontros sem alegações conseguiram gerar conversa ambiental, mas isso não comprovou transmissão de fofoca.

A revisão manual também encontrou falas com presença inventada (Capitu afirmou ter estado no cais sem registro acessível) e fonte inventada no retorno (atribuição a Escobar sem relato recebido correspondente). O motor permaneceu protegido contra criação de crimes/provas por essas falas; isso não torna a narrativa semanticamente correta. Esses achados motivaram correções no parser e nas projeções de álibis antes da rodada seguinte.

Tokens conhecidos das39 chamadas:72.443 de entrada e7.657 de saída; custo de tabela estimado USD0,01546065. A conta real pode ter créditos ou outras condições; não se afirma cobrança. Os valores usados (USD0,15/1M entrada, USD0,60/1M saída para Qwen3 32B em us-east-1) são os configurados a partir da [tabela AWS](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.json), consultada em2026-11-01.

## Rodadas após as correções

O formato de alegação e as políticas foram reutilizados durante as correções; não são trinta amostras independentes para estimar equilíbrio. As duas primeiras rodadas concentram Capitu e Virgília; a última amplia os atores para o elenco inteiro, portanto esta comparação é exploratória e não um experimento controlado entre versões. Os artefatos preservam cada estágio:

| Rodada narrativa | Chamadas remotas | Entrada/saída conhecidas | Estimativa USD | Extrações com alegações | Turnos sociais aceitos | Relato propagado com raiz preservada |
| --- | --- | --- | --- | --- | --- | --- |
| Inicial, `gameplay-before.json` | 39 | 72.443 / 7.657 | 0,01546065 | 0/10 | 4/10 | 0/10 |
| Parser tolera envelope exato e valida alegações individualmente, `gameplay-intermediate.json` | 40 | 81.741 / 6.167 | 0,01596135 | 10/10 | 1/10 | 0/10 |
| Citação/fonte canônicas na transmissão, `gameplay-final.json` | 40 | 83.313 / 6.975 | 0,01668195 | 10/10 | 9/10 | 8/10 |

A última rodada cobre os sete NPCs em dez amostras. As nove falas sociais aceitas incluem uma sem alegação selecionada, portanto a ausência de propagação nesse caso não indica perda de raiz. A décima proposta foi rejeitada por `intent: negotiate`, fora do enum permitido. Nas dez amostras finais houve resposta de retorno ao detetive, isolamento estrutural de memória e preservação dos fatos autoritativos da partida, apesar das conversas e viagens. O critério de invariância exclui os campos de leitura `server_time` e `seconds_remaining`; a comparação intermediária os incluía por engano e seus resultados desse critério são inconclusivos, não violações dos fatos do jogo.

Os nomes `source_attribution_valid` e `no_foreign_private_memory` no JSON representam verificações estruturais: IDs de emissores permitidos e ausência de conteúdo privado de outro ator no lote. **Não comprovam equivalência semântica da extração ou fidelidade da resposta livre.** A revisão humana encontrou na última rodada:

- A pergunta sobre Virgília ter visto Capitu no cais gerou uma interpretação do extrator de que “Floriano foi ao cais ontem”; outra pergunta sobre Bentinho ter visto Escobar inverteu o sujeito. Um trecho literal correto pode acompanhar uma paráfrase errada.
- O primeiro retorno de Capitu usou uma forma inesperada (“Mudou-me ao cais...”) que escapou à verificação local de presença. Respostas posteriores por vezes atribuíram uma informação diretamente ao detetive, embora ela tivesse chegado por outro NPC.
- A transmissão com trecho canônico preservou aquilo que foi selecionado e registrado, mas ainda depende da seleção de um conteúdo semanticamente correto na etapa anterior. Isso motivou a preservação literal adicional descrita na documentação de convivência.
- O tom variou: algumas falas mantiveram cautela e atribuição adequada, outras trocaram gêneros/títulos ou usaram ornamentos que prejudicaram a clareza. A qualidade narrativa ainda requer calibração; sucesso estrutural não equivale a uma aprovação geral de personagem.

Após esses achados, a integração passou a preservar como proposição compartilhável a fala original inteira, em uma citação atribuída ao emissor e destinatário reais; a paráfrase proposta pelo extrator deixa de substituir o que foi dito. Essa correção determinística impede que “Floriano foi ao cais” substitua uma pergunta original sobre outra pessoa. A rodada remota acima antecede esse último ajuste: sua evidência de regressão vem dos testes locais, e não de uma quarta rodada de inferência. A seleção de assuntos e a redação livre ainda dependem do modelo e permanecem sujeitas a revisão semântica.

As três rodadas somaram119 chamadas remotas com237.497 tokens de entrada e20.799 de saída, estimativa USD0,04810395. A chamada preliminar adicional usou48/32 tokens (estimativa USD0,0000264); total conhecido do experimento:120 chamadas e USD0,04813035. Partidas determinísticas não acessam o modelo. Falas recusadas pelo parser/guarda continuam incluídas nesses custos, pois a resposta do provedor foi recebida.

## Limites de equilíbrio observados

- Apresentar todos os objetos a todos os NPCs e interrogar o elenco ainda cabe no dia com os custos otimistas. Convém medir tempos humanos antes de fixar custos ou um orçamento de abordagens.
- Thresholds distintos não bastam para produzir dificuldade distinta: Capitu confessou tão cedo quanto Rubião ao acumular corroboração, negação e contradição de álibi.
- A variedade estratégica ainda é pequena. Máscaras e lapsos foram tornados independentes do papel no último refinamento, mas os cenários de encobrimento precisam ser comparados em amostras maiores.
- Observações de presença correspondem a um instante e à copresença próxima, não a vigilância contínua nem álibi da noite inteira. O jogador deve cruzá-las com objetos e fontes.
- Ainda falta comparar políticas de informação e de cooperação em amostras maiores, inclusive sob latência real, testemunhas indisponíveis, agenda social ativa e jogadores com tempo limitado.

## Verificação do runner

Cinco testes próprios verificam deduplicação de tipos na política pública, caminhada com relógio e comandos reais, confissão com provas, recusa de acusação sem suporte e prisão inocente seguida de soltura. Eles usam inferência simulada ou nenhuma inferência; a avaliação do Qwen é executada pelo script e registrada separadamente.
