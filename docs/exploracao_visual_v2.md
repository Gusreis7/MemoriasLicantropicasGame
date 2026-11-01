# Exploração visual: cenários compactos e saídas

O frontend usa uma tela lógica de 960 × 360, com cada local inteiro visível e câmera fixa. O mundo informa as mesmas dimensões. Não há seguimento da câmera, interpolação do fundo ou parallax. Cenário e decoração são criados uma vez na entrada do local e destruídos ao viajar; os snapshots de movimento atualizam a posição do jogador.

A implementação anterior já carregava o fundo somente na mudança de local e o Phaser 4.2.1 já limpava o framebuffer por padrão. O deslocamento verificável do fundo vinha da câmera que seguia o jogador com interpolação de 0,1, em um mapa de 1920 pixels. A revisão remove esse deslocamento, explicita `clearBeforeRender: true` e `preserveDrawingBuffer: false` e arredonda posições de desenho. A confirmação visual de ausência de rastro é feita no Brave, sem atribuir previamente o problema a falta de limpeza de frames.

Personagens usam o tamanho de exibição definido no manifesto, filtragem nearest e posições inteiras. Não se alternam poses diferentes de repouso a cada meio segundo; somente a caminhada do jogador utiliza os frames correspondentes. O manifesto atualizado pela frente de assets controla a maior resolução de exibição. Árvores, cidadãos figurantes, cães, gatos e pássaros são sprites de ambiente, sem papel no sorteio e sem alvos de conversa. Cada recorte do atlas cabe em sua caixa de composição preservando a proporção natural da imagem. Pequenos deslocamentos dos animais não alteram o fundo, o estado do mundo ou as pistas. `prefers-reduced-motion` mantém essa decoração parada.

## Contrato das passagens

`Location.exits` informa uma lista `{side, target_location_id, arrival_side}`. O mapa mantém viagem livre entre os cinco locais. Uma passagem pela borda envia `POST /api/v1/games/{id}/travel` com `{target_location_id, revision, exit_side}`. A API determina a chegada; o cliente não envia coordenadas, direção, papel ou revisão arbitrária. A mesma chamada com o local atual como destino solicita a outra ponta desse local; o mapa continua sem permitir selecionar o próprio local.

Ao caminhar até uma borda (x = 32 ou width − 32), o frontend aguarda também a posição confirmada próxima da borda (até 56 pixels). Interrompe o movimento e só então abre a escolha: destinos ligados, outra ponta do próprio local ou ficar. O servidor valida a passagem e determina o lado de chegada, com recuo de 96 pixels e orientação para dentro. Nenhuma viagem ocorre ao simplesmente tocar na borda. Cancelar desarma o convite até caminhar para dentro do cenário (mais de 72 pixels da borda); isso evita reabrir o menu continuamente. A escolha também funciona ao retomar um caso ou ao chegar pela passagem oposta.

O modal tem foco, Escape, contenção de Tab e botões de cancelamento. Teclado A/D e setas permanecem disponíveis, assim como o mapa e a abordagem. Controles laterais por toque ficam visíveis em dispositivos com ponteiro coarse. As legendas visuais “Caminhos” marcam os lados que possuem ligações.

## Validação

- Vitest: contratos da viagem pelo mapa e pela borda, posição prevista versus confirmada, abertura única, cancelamento, retorno para dentro e orientação dos limites.
- Playwright usando `/usr/bin/brave-browser`: preserva exploração, conversa, mapa, retomada e autenticação do administrador. Um fluxo adicional compara uma região estática do fundo antes/depois de caminhar, cancela e reabre a escolha, viaja pela ligação e solicita a outra ponta. Usa Redis e um LLM determinístico, sem AWS.
- Capturas de revisão: `artifacts/game-exit-choices.png` e `artifacts/game-world-static.png`.

Os assets raster e suas proveniências ficam sob responsabilidade da frente de arte; a cena espera `/assets/ambient/scene-life.png` e o atlas JSON de mesmo nome, com os frames `tree`, `dog`, `cat`, `bird`, `citizen-man` e `citizen-woman`.
