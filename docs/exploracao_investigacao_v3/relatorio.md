# Investigação v3: comparação antes/depois (concluído (100/100))

Este arquivo é gerado por `scripts/report_investigation_v3.py`. O conjunto after tem **100/100** linhas únicas e 100 pares por `case_id`. As 100 linhas after esperadas foram registradas. Baseline de código: `e2f2d62`; congelamento da variante: `9e7ca6f`.

## Escopo e limites

As partidas são de um jogador programado que consulta exaustivamente o caderno. Taxa de vitória não é taxa de vitória humana nem prova de equilíbrio. Qwen é não determinístico: os casos repetem papéis, perguntas e estados programados, mas 100 partidas não são observações estatisticamente independentes. A política é correlacionada ao tipo de pergunta por `i % 5`; não se pode interpretar diferenças entre políticas como efeito causal da voz. Vinte cenários definem confiança 20 e afinidade 12 antes da fala para exercitar a condição de confidência; isso não representa confiança adquirida de fato em quatro dias. Os IDs de jogo after são fixados aos da baseline e a variante contém itens pessoais adicionais selecionados de forma estável.

Os indicadores `actionable_proxy`, `evasive_proxy`, `metaphor_proxy` e `named_next_step` são heurísticas lexicais documentadas em `scripts/benchmark_investigation_v3.py`. “Acionável” é só proxy de utilidade: não certifica correção semântica, verdade, nem se o próximo passo é útil. As citações abaixo são amostras curtas pareadas, não avaliação manual completa.

## Resultados gerais

| fase | linhas | sondagens completas / falhas | partidas completas | vitórias | derrotas | recusas | mediana 1ª aceitação (dia) | chamadas LLM / 200 esperadas | mediana palavras | mediana latência s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| before | 100 | 100 / 0 | 100 | 79 | 21 | 155 | 1.0 | 200 / 200 | 35.0 | 2.46 |
| after | 100 | 99 / 1 | 100 | 40 | 60 | 400 | 2.0 | 200 / 200 | 35.0 | 2.83 |

Partidas e sondagens são contadas separadamente. Linhas com erro de execução não entram nas estatísticas de partida; falha de sondagem não é confundida com derrota. O denominador esperado de chamadas assume 100 sondagens por fase e duas solicitações por sondagem.

Falhas de sondagem: after case 16: llm_invalid_response.

## Partidas por política programada

| fase | política | jogos | vitórias | derrotas | recusas | mediana 1ª aceitação (dia) | sondagens concluídas/linhas | proxy acionável |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| before | common_rush | 20 | 14 | 6 | 64 | 3.0 | 20/20 | 0.40 |
| before | informed | 40 | 40 | 0 | 0 | 1.0 | 40/40 | 0.50 |
| before | single_source | 20 | 5 | 15 | 91 | 1.0 | 20/20 | 0.55 |
| before | unexamined | 20 | 20 | 0 | 0 | 1.0 | 20/20 | 0.95 |
| after | common_rush | 20 | 0 | 20 | 120 | — | 19/20 | 0.95 |
| after | informed | 40 | 40 | 0 | 40 | 2.0 | 40/40 | 0.95 |
| after | single_source | 20 | 0 | 20 | 120 | — | 20/20 | 0.95 |
| after | unexamined | 20 | 0 | 20 | 120 | — | 20/20 | 0.95 |

As políticas são `informed`, `common_rush`, `unexamined` e `single_source`, definidas pelo benchmark. `informed` é a única que inspeciona todas as pistas recolhidas; os demais filtros variam evidências/testemunhos anexados. Cada política se repete em posições que também determinam tipo de pergunta; a tabela é descritiva.

## Falas por tipo de pergunta e geral

| fase | grupo | n falas completas | acionável proxy | evasiva proxy | metáfora proxy | próximo passo nomeado | mediana palavras | mediana latência s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| before | overall | 100 | 0.58 | 0.06 | 0.05 | 0.18 | 35.0 | 2.46 |
| before | alibi | 20 | 0.95 | 0.05 | 0.00 | 0.00 | 26.5 | 2.36 |
| before | followup | 20 | 0.40 | 0.05 | 0.05 | 0.15 | 33.5 | 2.41 |
| before | help | 20 | 0.60 | 0.05 | 0.05 | 0.50 | 41.5 | 2.62 |
| before | object | 20 | 0.55 | 0.10 | 0.00 | 0.15 | 39.5 | 2.38 |
| before | relations | 20 | 0.40 | 0.05 | 0.15 | 0.10 | 40.5 | 2.60 |
| after | overall | 99 | 0.95 | 0.03 | 0.01 | 0.15 | 35.0 | 2.83 |
| after | alibi | 20 | 0.95 | 0.05 | 0.00 | 0.00 | 50.0 | 2.97 |
| after | followup | 20 | 0.90 | 0.00 | 0.00 | 0.15 | 36.5 | 2.95 |
| after | help | 20 | 1.00 | 0.00 | 0.05 | 0.05 | 32.0 | 2.76 |
| after | object | 20 | 0.95 | 0.05 | 0.00 | 0.20 | 34.0 | 2.84 |
| after | relations | 19 | 0.95 | 0.05 | 0.00 | 0.37 | 33.0 | 2.70 |

Taxas são proporções sobre sondagens de diálogo completas em cada grupo. Palavras e latência são medianas; a latência vem do registro do harness e não é medida de experiência do jogador.

## Descobertas desbloqueadas

| fase | conquista | partidas com desbloqueio |
| --- | --- | --- |
| after | escobar_affection | 1 |
| after | florenca_father | 6 |
| after | personal_trace | 40 |
| after | treatment_bentinho | 5 |

A tabela só conta IDs presentes em `game.achievements` nos JSONL; uma lista vazia significa nenhum desbloqueio registrado nesses cenários e não ausência de suporte no produto.

## Tokens e custo estimado

| fase | tarefa | chamadas | tokens de entrada | tokens de saída | USD estimado |
| --- | --- | --- | --- | --- | --- |
| before | total registrado | 200 | 781118 | 20647 | 0.12955590 |
| before | player_dialogue | 100 | 438083 | 6884 | 0.06984285 |
| before | session_master | 100 | 343035 | 13763 | 0.05971305 |
| after | total registrado | 200 | 423151 | 20033 | 0.07549245 |
| after | player_dialogue | 100 | 217503 | 6198 | 0.03634425 |
| after | session_master | 100 | 205648 | 13835 | 0.03914820 |

Tokens e custo somam exclusivamente `dialogue.usage.totals` uma vez por sondagem. A tabela por tarefa usa `by_purpose`, que reparte o mesmo total; não deve ser somada de novo ao total da fase. Os custos são estimativas calculadas pelo snapshot configurado de US$ 0,15/M tokens de entrada e US$ 0,60/M de saída, verificado em 2026-11-01. Isso não é preço atual nem fatura; chamadas sem metadados e cobertura anterior à medição limitam o total conhecido. Esperam-se 400 chamadas quando houver 100 sondagens em cada fase e duas chamadas registradas por sondagem.

before: modelo `qwen.qwen3-32b`, entrada US$0.15/M, saída US$0.60/M, verificação `2026-11-01`. after: modelo `qwen.qwen3-32b`, entrada US$0.15/M, saída US$0.60/M, verificação `2026-11-01`.

## Dez pares lidos manualmente

**Caso 0 · help · bentinho**  
Antes: “Sob suspeita, Escobar aparece com mais frequência por conta de Capitu. Rubião talvez compreenda…”  
Depois: “Vou dizer uma coisa concreta: Capitu se encontra com Escobar nos parques e no…”  
A resposta depois nomeia a ligação Capitu–Escobar e sugere falar com ambos; antes, o encaminhamento recai em Rubião. O proxy acionável marca as duas respostas, sem julgar qual encaminhamento é melhor.

**Caso 1 · relations · bentinho**  
Antes: “Bem que você me pergunta... O Bacamarte tem receitado remédios, mas eu prefiro tratar…”  
Depois: “Uma coisa eu lhe digo: Bentinho faz acompanhamento com Bacamarte, mas resiste às consultas…”  
Antes, Bentinho fala em primeira pessoa sobre a resistência ao tratamento; depois, a fala enumera a lembrança autorizada e indica Bacamarte e Bentinho. A formulação posterior é mais prescritiva, mas soa mais resumida.

**Caso 3 · object · bentinho**  
Antes: “Já vi caixas iguais em mãos de muitos que fumam ou acendem velas sem…”  
Depois: “Uma coisa eu lhe digo: Sobre Caixa de fósforos: Já vi Rubião com um…”  
As duas falas recusam tratar item comum como autoria. Depois, a resposta associa o tipo a Rubião e aponta as anotações do caderno; isso continua sendo reconhecimento de objeto semelhante, não prova de quem deixou o exemplar.

**Caso 7 · alibi · capitu**  
Antes: “Estava em minha cabana, sozinha, tratando de assuntos particulares. Naquele período, ninguém me via.…”  
Depois: “Estava na Cabana da Capitu naquela noite, sem companhia que confirme. Vi Virgília Neves…”  
Depois, Capitu menciona ter visto Virgília, informação ausente antes; também delimita que não sabe onde Virgília esteve depois. O proxy de evasão sobe por essa ressalva lexical, não por uma avaliação de sinceridade.

**Caso 9 · followup · capitu**  
Antes: “Vi Escobar com botões semelhantes, mas nada que o ligue a crime algum. A…”  
Depois: “Posso lhe ajudar com isso: Sobre Botão de osso: Já vi Escobar com um…”  
A resposta posterior nomeia Escobar como alguém que já teve objeto semelhante e sugere comparar depoimentos. A anterior traz uma pergunta sobre autoria e intenção; ambas permanecem sem atribuir o objeto ao crime.

**Caso 14 · followup · escobar**  
Antes: “Lenços de algodão são comuns, e este não me diz nada específico. Sobre perguntas:…”  
Depois: “Não sei de quem é o lenço. Pergunte a Capitu se reconhece um lenço…”  
A resposta posterior recomenda uma pessoa específica para reconhecer lenços. A fala anterior diz que o lenço é comum e orienta buscar quem o viu; a diferença observada é a especificidade do contato sugerido.

**Caso 15 · help · escobar**  
Antes: “Capitu sofre com o ciúme de Bentinho, mas Virgília talvez observe melhor o comportamento…”  
Depois: “Conheço Bentinho e Capitu há anos, e sei que eles são casados, embora ele…”  
Depois, Escobar dá contexto mais explícito sobre casamento e ciúme, mas é mais longa. O detector de metáfora marca “sombra de um cão” por palavra-chave, exemplo de que o proxy não interpreta contexto.

**Caso 20 · help · escobar**  
Antes: “É claro que quero ajudar. Se você quiser entender os moradores melhor, converse com…”  
Depois: “Bentinho e Capitu são casados, mas ele anda ciumento da proximidade dela comigo. Pergunte…”  
Depois, a resposta comprime o tema do ciúme e termina em pergunta a Bentinho; antes, oferecia outros contatos. O próximo-passo proxy cai por seu padrão lexical estreito, apesar da sugestão textual.

**Caso 21 · relations · rubiao**  
Antes: “Minha Florença brilha como um raio, embora me evite. Desejo ser-lhe útil, mesmo à…”  
Depois: “Isso eu posso lhe contar: Rubião tenta aproximar-se de Florença, embora ela não corresponda…”  
Antes, Rubião responde com uma imagem afetiva breve; depois, descreve a falta de reciprocidade e oferece continuar a conversa. Isso compara duas formulações do tema, sem validar a leitura do personagem.

**Caso 30 · help · virgilia**  
Antes: “O principal é que Rubião insiste em cortejar Florença, embora ela nem lhe dê…”  
Depois: “Minha filha, se é assim que quer ajudar, saiba que Florença anda furiosa com…”  
Antes, Virgília sugere ouvir Florença sobre Rubião; depois, descreve o ressentimento de Florença contra Bacamarte e sugere perguntar. A diferença muda o foco narrativo e não demonstra que uma versão seja verdadeira.

## Revisão qualitativa crítica: fidelidade e voz

O `actionable_proxy` marcou 94 de 99 respostas after completas. A amostra seguinte mostra por que esse 94/99 não é taxa de fidelidade: é um sinal lexical de possível utilidade, não uma checagem de suporte ou de coerência do personagem.

- **Caso 34 · Virgília / follow-up sobre cera:** os suportes autorizados incluem “Já vi Dr. Bacamarte com um objeto igual” e assuntos sobre Florença, mas não mencionam Brás Cubas afogado nem vapor. A resposta acrescenta “se viajava com vela na mesma linha do vapor que afogou Brás”. Essa associação concreta não aparece nos suportes que conferi e deve ser tratada como conteúdo inventado, não como pista.
- **Caso 81 · Virgília / relações:** os suportes registram que Bentinho e Escobar estudaram juntos no seminário (“Bentinho e Escobar estudaram juntos no seminário e mantiveram uma ligação antiga”). A fala after transfere a lembrança para “A amizade entre nós é de longa data, de seminário” e parece atribuir a história a Virgília e Florença. A relação de seminário foi atribuída ao par errado.
- **Caso 1 · Bentinho / relações:** antes, Bentinho responde em primeira pessoa sobre resistir ao tratamento. Depois, fala de si em terceira pessoa (“Bentinho faz acompanhamento…”) e termina orientando Floriano a conversar “com Bentinho”, isto é, com o próprio interlocutor. A memória do tratamento está autorizada, mas a forma é uma piora clara de voz e continuidade.
- **Caso 21 · Rubião / relações:** depois, Rubião repete de perto o suporte autorizado sobre a investida não correspondida (“Rubião tenta aproximar-se de Florença…”). Isso tem âncora, mas a formulação em terceira pessoa soa como resumo de ficha e não como uma fala dele. O actionability proxy aceita a resposta sem medir naturalidade.

Esses casos foram conferidos contra `authorized_supports` em ambas as linhas JSONL; apenas as afirmações indicadas como não apoiadas foram julgadas sem suporte. A revisão é uma leitura qualitativa pequena e não estima prevalência. Próximos passos: aumentar a checagem automática de cada afirmação contra os suportes explícitos, validar a identidade gramatical da primeira pessoa e inspecionar manualmente uma amostra maior por tipo de pergunta antes de usar o proxy para decisões de qualidade.

Uma correção posterior ao congelamento `9e7ca6f` está sendo feita em separado por outra agente: renderização determinística e descoberta/conquista ligada à fala em primeira pessoa. Ela não altera os 100 registros after que este relatório resume; a versão corrigida precisará de uma nova execução/avaliação para aparecer nos dados.

## Reprodutibilidade e hash SHA-256

| arquivo | SHA-256 |
| --- | --- |
| docs/exploracao_investigacao_v3/before.jsonl | 70437ebc04824c1fbc17af6b92511ab8142666b32dd80f62be38042fb9160d4f |
| docs/exploracao_investigacao_v3/after.jsonl | bbc7db38a7eef10e8947ad4d6f004ebaacbf11351610d8a46b5685fd466a5b2f |
| scripts/benchmark_investigation_v3.py | 527d63c4c575b041610063ca9ccc48aeef252698768e83f58d616b9b65ffb6c2 |
| scripts/report_investigation_v3.py | 6581fa9d127fe1a1d758171a13d36b0c79dd7f96e783f2651a0d95c6ae1a7c56 |

O resumo `resumo.json` guarda os mesmos hashes, contagens e métricas em formato legível por máquina; `resultados.csv` permite filtrar políticas, pergunta e tarefa de uso. Para atualizar o relatório quando `after.jsonl` chegar a 100 linhas, execute:

```sh
python scripts/report_investigation_v3.py --root /caminho/para/repo --output-dir /caminho/para/docs/exploracao_investigacao_v3
```

A entrada lida deve ser `docs/exploracao_investigacao_v3/{before,after}.jsonl` dentro de `--root`; a saída é escrita somente em `--output-dir`.

## Regras de evidência alteradas

A versão nova limita comuns a 0,25 cada e teto conjunto 0,5; singulares valem 1 e têm teto 2; exclusivos valem 3 por tipo. Fontes externas distintas somam 0,5 cada até 1, e uma contradição pública válida de álibi pode somar 0,75. Custódia exige pontuação mínima 5, dois tipos ligados ao acusado, exclusivo examinado com vínculo físico à cena e duas fontes externas; alternativa: uma fonte externa e uma contradição pública de álibis. O exame repetido é idempotente e não transforma comuns/singulares em prova de maior peso. A especificação completa está em `docs/evidencias_especificidade_v3.md`.
