# Animações, cadeia e edição de vitória

## Personagens e animais

Os sprites dos NPCs permanecem vivos entre atualizações de coordenadas. Apenas mudanças de composição, atividade ou fala refazem a composição visível; a chegada de novas posições interpola os mesmos objetos e não reinicia a sequência de pernas. A caminhada usa os frames existentes dos personagens, como a do jogador. A identificação do NPC continua vindo do estado público, sem antecipar papéis.

Cães e gatos têm quatro poses de caminhada, aves têm quatro poses de batida de asas. O atlas `assets/ambient/animals-walk.png` contém quatro colunas e três linhas; `animals-walk.json` define os frames. Os animais fazem trajetos curtos, viram ao retornar e as aves oscilam em altura. A preferência por redução de movimento mantém os figurantes em uma pose estática.

## Cadeia

A detenção abre uma vista própria da delegacia, com o personagem correto dentro das grades e o relógio da partida. Durante o dia pode-se voltar à investigação. À noite, a vista da cadeia acompanha a espera sem aceitar fechamento por Escape ou ações diurnas.

O modelo não decide transformação. A imagem do lobisomem aparece somente após o servidor confirmar vitória por detenção. A cena faz a transição entre o personagem humano e quatro poses do monstro e então apresenta o jornal final. Se a noite liberar um inocente, a porta abre, ele caminha para fora e o Clarim da manhã aparece. Reabrir um caso durante custódia retoma a espera; recarregar uma partida já vencida pode reapresentar a revelação confirmada.

As durações visuais (aproximadamente3,4 segundos para a revelação e2,5 para a soltura) são locais e não avançam ou resolvem o relógio do motor. O término da apresentação usa prazo de interface, evitando travar a edição final quando o relógio de animação do canvas é suspenso pelo navegador. Redução de movimento encurta a sequência e dispensa os movimentos automáticos.

## Jornal

Cada edição pública recebe uma chave `illustration`, compatível com registros anteriores por valor padrão. Crimes no Cais usam a ilustração portuária; Casa Verde/cabana usam jardim; outros locais usam a rua existente. As imagens são ilustrações de arquivo e não comprovam acontecimentos adicionais.

Vitórias por detenção, confissão e assembleia persistem uma edição que celebra Floriano e informa o destino do culpado. A página final tem masthead, manchete, ilustração monocromática, texto e botão para iniciar outro caso; o motor permanece encerrado. Prisão e transformação noturna mantêm a expulsão prevista pelas regras; confissão registra custódia e assembleia registra expulsão. O jornal identifica a pessoa correta após o desfecho.

## Arte e proveniência

Geradas com **image_gen built-in**, usando os sprites e a imprensa existentes como referências de estilo:

- `frontend/public/assets/cinematics/werewolf.png` e `werewolf.json`: quatro poses de lobisomem, fundo transparente.
- `frontend/public/assets/cinematics/jail.png`: fundo estático da cadeia; grades em primeiro plano são objetos do jogo.
- `frontend/public/assets/ambient/animals-walk.png` e `animals-walk.json`: doze poses com alpha, inclusive edição de remoção do fundo.
- `frontend/public/assets/press/editions.png`: atlas2×2 de ilustrações de cais, jardim, captura e celebração. Na celebração, Floriano ocupa o centro com a mesma identidade visual do sprite do jogador: pele morena, cabelo escuro, bigode curto, casaco castanho, colete escuro e camisa clara. Ele saúda a cidade com a mão vazia; não usa nem ergue cartola.

Prompts completos e fontes: [prompts.json](../frontend/public/assets/cinematics/prompts.json). Os assets gerados foram copiados para o repositório; o runtime não depende do diretório de geração.

## Verificação

Testes backend cobrem edição extraordinária persistida por vitória, nome do culpado e compatibilidade com os ciclos existentes. Brave cobre detenção, espera noturna, bloqueio de Escape, transformação, página de vitória e soltura antes do jornal da manhã. Capturas locais: `artifacts/custody-waiting.png`, `custody-transformation.png` e `clarim-victory.png`. A suíte não exige chamadas AWS.

Resultado: **529 testes Python** com Redis real isolado, **40 testes frontend**, build TypeScript/Vite e **onze fluxos Brave** aprovados. Arte com alpha e dimensões dos atlas conferidas; nenhuma chamada AWS foi necessária para as validações desta entrega.

O build servido pelo Docker também foi conferido no Brave nas portas7077/7078, incluindo carregamento das artes, diálogo protegido, interrogatório e sessão admin.
