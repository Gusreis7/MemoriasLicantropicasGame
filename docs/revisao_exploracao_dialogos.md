# Revisão de exploração e diálogo

Execução autorizada pelo autor em novembro de 2026. Integração em `feat/revisao_exploracao_dialogos`, com promoção para `develop` após os testes; `main` permanece sem alterações.

## Frentes e contratos

| Frente | Branch | Responsabilidade |
| --- | --- | --- |
| Coordenação | `feat/revisao_exploracao_dialogos` | Mundo compacto, conexões validadas, assets, integração e Docker |
| Parser | `fix/contrato_respostas` | Normalização antes da memória/API, contrato da fala e histórico legado |
| Guarda | `feat/guarda_dialogos` | Política determinística de entrada/saída, sem inferência ou ferramentas |
| Exploração | `feat/exploracao_cenarios` | Canvas fixo, escolha de saídas, figurantes, controles e testes Brave |

Os agentes trabalham em worktrees isoladas. O parser consome `DialogueGuard.inspect_input(text)` e `inspect_output(text, private_markers=())`, que retornam `GuardDecision(allowed, reply, reason)`. O motivo é interno; a recusa pública é uma fala diegética segura. Classificar uma tentativa não executa ações nem muda o estado da partida. O adaptador Mantle continua sem ferramentas e recusa tool calls.

O transporte LLM é separado do conteúdo do personagem. A saída aceita fala simples ou o envelope estrito `{remetente, fala}`, com remetente validado; a API e o Redis recebem somente a fala. Resposta inválida gera erro genérico; conteúdo bloqueado recebe recusa segura. Tentativas bloqueadas não entram no contexto futuro como instruções. Veja [contrato_respostas.md](contrato_respostas.md) e [guarda_dialogos.md](guarda_dialogos.md).

## Mundo compacto e passagens

Os cinco cenários têm 960 × 360, chão y300 e faixa x32–928. A câmera é fixa: apenas os personagens e a decoração móvel mudam de posição. O fundo é uma imagem estática por local. Sprites principais passam a 64 × 88; suas fichas e aparência permanecem independentes do papel secreto.

`LocationPublic.exits` contém `{side, target_location_id, arrival_side}`. A mesma lista orienta o menu e a validação do servidor. `TravelRequest` recebe `exit_side` opcional: omitido, preserva a viagem pelo mapa; informado, exige proximidade da borda (56px) e conexão válida. A chegada fica 96px para dentro da borda definida pelo servidor, voltada para o cenário. O jogador também pode escolher ir à outra ponta do mesmo local; isso exige uma saída válida pela posição e nunca ocorre automaticamente. A sequência de movimento e o sorteio permanecem preservados. Eventos registram origem, destino e bordas na transação CAS.

Praça liga Cabana/Café pela esquerda e Casa Verde/Cais pela direita. Cabana e Café se ligam pelas respectivas bordas esquerdas; Casa Verde e Cais, pelas direitas. Todas as ligações são recíprocas. O menu permite ficar, sem abrir repetidamente antes de o jogador recuar.

Partidas antigas podem conter x acima de928. A leitura do repository projeta essas posições para a faixa atual, sem gravar no GET e sem ressorteio. A próxima ação grava a projeção por CAS. O modelo de persistência mantém o limite legado apenas para conseguir ler esses registros.

Figurantes, árvores, cães, gatos e pássaros são decoração local. Não entram no elenco de sete suspeitos, não recebem papel, conversas ou capacidade de criar fatos da investigação.

## Verificação

Testes cobrem parser/guarda, privacidade, respostas adversariais, conservação do estado e eventos, conexão por borda, retomada, movimentação e interface em Brave. As chamadas de modelo dos testes usam stub; não é necessário consumir inferência real para esta revisão.
