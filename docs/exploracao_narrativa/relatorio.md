# Exploração das mecânicas narrativas: resultados e custo

Relatório gerado de arquivos JSONL existentes. Este comando não executa partidas, não faz inferências e não consulta preços.

## Escopo e contabilização

Foram contabilizados **100 cenários/tentativas**: 21 inicializações com erro, 72 partidas completas de regras e 7 encontros reais com Qwen. Continuações dos mesmos encontros não contam como novas partidas; seus custos entram integralmente em fases separadas.

As 21 primeiras tentativas falharam no setup porque o método `seed` colidia com um atributo inteiro. Os registros foram preservados e não entram no denominador de vitórias das partidas completas. Das 72 partidas posteriores, as primeiras 21 são calibragem; as 51 restantes são o conjunto posterior à correção da extração de “matou”. As fases foram separadas cronologicamente, sem excluir as derrotas anteriores.

## Regras: calibragem de 21 partidas completas

| Política | Partidas | Vitórias | Derrotas | Erros | Métodos |
| --- | ---: | ---: | ---: | ---: | --- |
| assembly_informed | 4 | 4 | 0 | 0 | assembly: 4 |
| detention_informed | 4 | 4 | 0 | 0 | detention: 4 |
| hostile_rash | 4 | 0 | 4 | 0 | player_expelled: 4 |
| natural_confession | 3 | 0 | 3 | 0 | survival: 3 |
| passive | 3 | 0 | 3 | 0 | survival: 3 |
| rash | 3 | 3 | 0 | 0 | detention: 3 |

## Regras: conjunto posterior de 51 partidas completas

| Política | Partidas | Vitórias | Derrotas | Erros | Métodos |
| --- | ---: | ---: | ---: | ---: | --- |
| assembly_informed | 8 | 8 | 0 | 0 | assembly: 8 |
| detention_informed | 8 | 8 | 0 | 0 | detention: 8 |
| hostile_rash | 8 | 0 | 8 | 0 | player_expelled: 8 |
| natural_confession | 9 | 9 | 0 | 0 | confession: 9 |
| passive | 9 | 0 | 9 | 0 | survival: 9 |
| rash | 9 | 9 | 0 | 0 | detention: 9 |

## O que os resultados demonstram

- As partidas completas registraram 0 ocorrências de erro em ações e 0 vitórias atribuídas a confissões de inocentes. Essa contagem cobre somente as transições realmente exercitadas.
- A política informada coleta objetos e consulta todas as testemunhas acessíveis; seu alto aproveitamento mostra que o conjunto de pistas resolve esses cenários. Não mede a dificuldade para uma pessoa que conversa livremente nem prova equilíbrio humano.
- A confissão natural foi alimentada por uma persona programada que sabe o próprio papel e devolve uma frase de confissão/rendição para o culpado. Isso verifica a ligação chat → mestre → resolução, mas não mede a probabilidade de convencer um Qwen real a confessar.
- A política `hostile_rash` aplica previamente 12 eventos hostis fortes a todos os NPCs. Ela verifica a possibilidade de expulsar Floriano sob relações deterioradas; não estima a frequência dessa derrota em conversa cotidiana.
- A política `rash` faz uma primeira acusação precipitada, depois passa a coletar pistas e usar a política informada de prisão. Suas vitórias não demonstram sucesso de acusações aleatórias durante toda a partida.
- A semeadura produziu assuntos autorais e raízes de fofoca. Essas partidas não executam uma longa rede autônoma de conversas; propagação, confidências e reputação precisam também dos testes específicos e de observação de partidas humanas.

## Qwen real: custo por fase e qualidade

| Fase | Respostas concluídas / registros | Chamadas | Entrada | Saída | Tokens desconhecidos (chamadas) | Custo conhecido USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| live.jsonl | 7/7 | 14 | 33685 | 3362 | 0 | 0.00706995 |
| live_followup.jsonl | 7/7 | 14 | 35691 | 1900 | 0 | 0.00649365 |
| live_quality.jsonl | 7/7 | 14 | 58381 | 1969 | 0 | 0.00993855 |

| Tarefa (todas as fases reais) | Chamadas | Entrada | Saída | USD conhecido |
| --- | ---: | ---: | ---: | ---: |
| player_dialogue | 21 | 96877 | 4302 | 0.01711275 |
| session_master | 21 | 30880 | 2929 | 0.00638940 |

Total registrado: **42 chamadas**, **127757 tokens de entrada**, **7231 de saída**, **USD 0.02350215** de custo conhecido estimado. Resumos sem uso registrado: 0; chamadas sem tarifa: 0. Custo é estimativa dos tokens observados, não extrato da fatura, crédito ou gratuidade.

As fases usam repositórios de medição separados e carregam somente as falas anteriores para continuar o mesmo encontro; seus contadores são incrementais por fase, não totais cumulativos que devam ser deduplicados.

Leitura qualitativa das primeiras fases: as respostas iniciais foram extensas, incluíram narração de gestos e locais não autorizados (por exemplo, a escultura da Cachoeira). A continuação encurtou as falas, mas preservou deriva narrativa: Capitu ainda chamou Floriano de “delegado”, Escobar revelou afeto íntimo e surgiram locais/fontes inventados. Uma resposta concluída tecnicamente não equivale a resposta aprovada em naturalidade ou fidelidade.

A terceira fase contém 7/7 registros após a revisão de qualidade. Os sinais automáticos abaixo são triagem; exigem leitura das respostas e não certificam ausência de alucinação.
Palavras por resposta concluída: média 35.7; máximo 78. Referências a delegado: 0. Respostas acima de 120 palavras: 0. 
O mestre propôs reparo em 6/7 respostas; problemas identificados: {'unauthorized_confidence': 2, 'narrator_style': 3, 'wrong_address': 1}.
A leitura manual ainda encontrou alegações não sustentadas no reparo de Florença (Capitu copiando seus versos) e na resposta de Bacamarte (visitas noturnas e associação com escuridão). O reparo melhorou concisão e tratamento, mas não aprovou o grounding narrativo: uma correção do LLM pode introduzir nova invenção.

## Influência algébrica de argumentos e vínculos

Avaliações pontuais da função real `vote_scores`; não são novas simulações. Limiar 0.50, margem mínima 0.08.

| Condição | Prova | Argumento | Score acusado | Score Floriano | Voto |
| --- | ---: | ---: | ---: | ---: | --- |
| neutro, argumento fraco | 0.40 | 0.00 | 0.3880 | 0.0620 | abstenção |
| neutro, argumento forte | 0.40 | 1.00 | 0.5050 | 0.0000 | escobar |
| amigo protegido, prova moderada | 0.65 | 0.70 | 0.4199 | 0.0000 | abstenção |
| inimigo, mesma prova moderada | 0.65 | 0.70 | 1.0000 | 0.0000 | escobar |
| hostilidade a Floriano, prova fraca | 0.10 | 0.10 | 0.1740 | 0.9260 | player |
| amigo protegido, prova forte | 1.00 | 0.80 | 0.6836 | 0.0000 | escobar |
| neutro, eloquência sem prova | 0.00 | 1.00 | 0.2170 | 0.0300 | abstenção |

Uma fala coerente pode alterar voto na fronteira; simpatia protege e ressentimento favorece acusação. Prova forte supera amizade moderada, enquanto hostilidade a Floriano pode inverter o alvo. Sem prova, eloquência isolada não ultrapassa o limiar no caso neutro. Isso é propriedade das fórmulas, não resultado de um teste humano.

## Projeção de custo por partida

Base observada: 7 trocas concluídas de `live_quality.jsonl`; média USD 0.00141979 por troca, incluindo tarefas medidas do mestre/reparo. Vinte trocas com a mesma distribuição custariam aproximadamente USD 0.02839586.

| Hipótese adicional | Chamadas | Entrada/chamada | Saída/chamada | USD estimado |
| --- | ---: | ---: | ---: | ---: |
| social_speech | 16 | 1500 | 100 | 0.00456 |
| knowledge_extraction | 8 | 2000 | 250 | 0.0036 |
| assembly_debate | 1 | 3000 | 700 | 0.00087 |

Total ilustrativo: **USD 0.03742586**. Os extras são hipóteses de tamanho de contexto, não tokens medidos: 16 falas sociais, 8 extrações e uma chamada de assembleia. O total não é limite de cobrança: contexto crescente, retries, falhas e reparos mudam o custo. Não foi cobrada inferência nos 72 jogos programados; o custo conhecido do provedor nesta exploração vem dos encontros reais.

Snapshot usado: `qwen.qwen3-32b`, entrada USD 0.15/milhão, saída USD 0.60/milhão; consulta registrada 2026-11-01. Fonte registrada: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.json. Não houve nova consulta de tarifa.

## Critérios de aceite e pontos ainda abertos

- **Passou nos cenários exercitados:** fechamento por assembleia/prisão/confissão programada, derrota por sobrevivência e expulsão de Floriano; sem promoção de confissão de inocente registrada nessas partidas.
- **Falhou e foi corrigido:** colisão do método `seed` no setup; reconhecimento de “matou” na admissão natural. As falhas anteriores permanecem nos artefatos.
- **Não aprovado como equilíbrio humano:** políticas informadas muito eficientes, hostilidade forte concentrada em 12 eventos programados e pequenas amostras por personagem. O holdout usa código corrigido, mas a distribuição de políticas e cenários é conhecida pelo autor da exploração.
- **Qualidade narrativa inicialmente falhou:** excesso de narração, intimidade prematura e detalhes inventados nas amostras reais. A terceira fase precisa de leitura manual; custo/latência não bastam como aceite.
- **Próxima avaliação recomendada:** sessões humanas sem acesso ao papel secreto, mistura gradual de cordialidade e hostilidade, fofocas transmitidas ao longo do dia, confidências abertas por ações concretas e argumentos livres na assembleia. Não foram iniciadas novas partidas para ampliar esta exploração.

## Reprodução do relatório

`uv run python scripts/summarize_narrative_exploration.py --root .` lê os artefatos e regrava relatório, resumo JSON e CSV. Não executa o runner de partidas. O resumo registra SHA-256 dos arquivos de entrada e da função de votação usada na análise algébrica.
