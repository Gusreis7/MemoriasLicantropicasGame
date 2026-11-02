# Interrogatórios, álibis e confissão

O detetive pode pedir uma versão oficial sobre local, companhia e atividade em um dia/período. Essa versão permanece no caderno e no contexto do NPC. Uma conversa livre continua sendo discurso; somente o comando oficial acrescenta o registro estruturado usado no confronto.

## Endpoints

- `POST /api/v1/games/{id}/interrogations`: `{npc_id,day,period:"night"|"day"}`. Noite anterior ao primeiro dia usa `day:0`. Noite ainda não ocorrida é inválida. Período histórico sem registro produz desconhecimento; não é reconstruído pelo local atual.
- `POST /api/v1/games/{id}/confrontations`: `{npc_id,evidence_ids:[],testimony_ids:[],interrogation_ids:[]}`. Incluir pelo menos a versão do próprio alvo. Cada morador pode ser confrontado uma vez por dia. Os IDs devem pertencer à partida e os depoimentos selecionados devem acompanhar seus vestígios.

Ambos retornam `CasePublic`, agora com `interrogations`, `confrontations` e `ending.method` (`detention`, `confession`, `survival`). Exigem dia ativo, NPC vivo, livre, parado e a até64px no mesmo local. Se estiver em encontro social, aborde-o primeiro para interromper o encontro; o endpoint direto não ignora a reserva social.

## Fonte e conhecimento

O caso inicial tem um cenário histórico explícito da noite0, baseado nas posições canônicas e presença do assassino na cena inicial. Novas noites registram o estado factual na resolução; snapshots diurnos surgem na primeira pergunta do dia ou na fronteira do anoitecer. São observações de um instante, sem comprovar presença durante toda a noite. Companhias exigem distância de até64px; observadores só veem pessoas no mesmo cenário. Mortos anteriores, presos e personagens em trânsito não ganham presença fictícia no local de origem. O registro público de soltura continua no jornal; falta de registro individual é assumida como lacuna.

O lobisomem consciente oferece uma versão de encobrimento estável. Civis ajudam conforme sua disposição e lembranças: alguns limitam observações ou preservam companhias privadas. Bacamarte admite lacunas tanto civil quanto lobisomem; desconhecimento e redação não funcionam como assinatura do papel. A projeção pública não contém `truthful`, `source_record_ids`, atividades privadas, pressão ou dificuldade. A função `npc_interrogation_context` oferece ao diálogo e à convivência apenas versões do ator, seus confrontos e presenças que observou.

## Confronto e dificuldade

O confronto usa apenas elementos apresentados: exige a corroboração mínima já usada pelo delegado (dois tipos de vestígio ligados ao acusado), uma versão própria e inconsistência entre negação de reconhecimento/posse e testemunho associado ou entre álibi e observação de outro NPC sobre o mesmo período. A inconsistência é entre versões, não uma leitura pública da verdade secreta.

Objetos pontuam uma vez por tipo: exclusivo3, singular2, comum1; corroboração soma1; testemunhas adicionais independentes somam até2; conflito de reconhecimento soma2 e conflito de álibi soma2. A dificuldade privada é Rubião5, Bentinho6, Florença7, Virgília7, Escobar8, Capitu9, Bacamarte10. As faixas são valores iniciais de calibração, sem promessa de equilíbrio populacional.

O motor confirma confissão somente se o alvo for o lobisomem e a pressão atingir sua dificuldade. A mesma recusa genérica é possível por insuficiência ou inocência. Confessar encerra a partida em vitória, registra a entrega ao delegado e remove o lobo das posições públicas. Caso, estado da partida, mundo e eventos são gravados na mesma transação; o TurnService reavalia a seleção antes de autorizar a exceção de vitória diurna. A vitória por prisão e transformação noturna permanece disponível.

Uma frase do LLM ou do jogador dizendo que alguém confessou não dispara vitória. A primeira versão usa fala oficial determinística; o LLM recebe as versões e interpreta o diálogo ao redor delas. Variação de prosa com modelo real e circulação de álibis como relatos são avaliadas separadamente na simulação.

## Validação

`tests/test_interrogations.py` cobre estabilidade, privacidade, fonte histórica, desconhecimento civil, trânsito/prisão, abordagem social, contrato HTTP, os sete limiares, evidência insuficiente, limitação diária, tentativa de forjar vitória e transação final. Rodar com as suítes de investigação e turnos. Neste ambiente, as rotas HTTP exigiram o heartbeat temporário já usado na entrega de convivência, sem alteração na aplicação.
