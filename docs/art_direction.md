# Direção de arte — personagens e retratos

Frente implementada em `feat/assets_personagens`. Imagens finais em `frontend/public/assets/characters/` e `frontend/public/assets/portraits/`, produzidas com **image_gen built-in**. Prompts e origem dos arquivos estão em `docs/provenance_personagens.json`.

## Fonte e escolhas artísticas

As descrições físicas seguem os rascunhos do autor em `/home/gustavoreis/Documentos/QuemEOLobisomem`, consultados sem alterações. A tabela abaixo distingue os atributos documentados dos complementos artísticos aprovados no plano visual.

| ID | Atributos documentados preservados | Complementos de desenho |
| --- | --- | --- |
| `player` | Floriano ainda não possui descrição física na fonte | Homem adulto de pele morena, cabelo escuro, pequeno bigode, casaco castanho, colete escuro, camisa clara e caderneta |
| `bentinho` | 45 anos, branco, cabelo cacheado e bagunçado | Cachos escuros, sobrecasaca carvão, colete verde, postura tensa e expressão desconfiada |
| `capitu` | 40 anos, jovial, ruiva e olhos dourados | Pele de tom claro quente, cabelo parcialmente preso, saia teal, corpete vinho e xale oliva, sem adereços caricatos |
| `escobar` | 45 anos, moreno, cacheado, olhos verdes | Cachos escuros, barba/bigode aparados, paletó marinho, colete ameixa, expressão afável |
| `rubiao` | 30 anos, moreno, cabelo liso e olhos escuros | Cabelo escuro de lado, bigode discreto, paletó ocre e colete ferrugem, expressão ansiosa por agradar |
| `virgilia` | 33 anos, branca, loira e olhos castanhos | Coque baixo, vestido ameixa, xale violeta, gola marfim e expressão sociável |
| `florenca` | 28 anos, negra e olhos âmbar | Cabelo crespo preso, casaco mostarda, saia verde-oliva e postura determinada |
| `bacamarte` | 35 anos, alto, moreno, óculos e jaleco | Cabelo escuro penteado, bigode fino, óculos redondos, jaleco marfim e colete azul-petróleo |

“Moreno” permanece o termo da fonte, sem atribuição racial adicional. Roupa, penteado e cores não especificadas são escolhas do projeto. A aparência não varia com o papel sorteado: nenhuma imagem, aura ou arquivo denuncia um lobisomem.

## Estética e escala

Sprites e retratos têm linguagem raster de pixel art expressiva, paleta terrosa, contorno escuro e trajes de época. As imagens originais têm resolução maior que as células lógicas do jogo; não foram substituídas por vetores ou figuras provisórias. O frontend deve usar filtragem nearest-neighbor/pixelArt e a escala definida no manifesto.

Os sete NPCs mantêm sheets PNG RGBA com seis poses: duas de idle e quatro de caminhada. Floriano usa uma sheet própria com dez poses: duas de idle e oito fases de caminhada, alternando contato, apoio e passagem das duas pernas, com braços em oposição. As figuras ficam voltadas para a direita; espelhar horizontalmente fornece a direção esquerda. O ciclo do jogador roda a 12 quadros por segundo enquanto há deslocamento e retorna ao repouso ao parar ou alcançar uma borda. Prompt, origem e medidas do novo atlas estão em [player-walk-prompts.json](../frontend/public/assets/characters/player-walk-prompts.json).

Os retratos dos sete suspeitos reutilizam a respectiva sheet como referência de identidade. Olhos dourados de Capitu, verdes de Escobar e âmbar de Florença são legíveis no retrato. O jogador não possui retrato de diálogo. Brás Cubas possui um retrato próprio para a primeira edição do Clarim, conforme a revisão abaixo.

## Retrato de Brás Cubas — revisão de estilo

O retrato inicial do Clarim usa `assets/portraits/bras_cubas.png`, refeito com **image_gen built-in** a partir dos retratos de Bentinho e Escobar como referências diretas de estilo. A versão anterior serviu apenas de referência de identidade. O desenho acompanha o elenco com cabeça levemente ampliada, olhos expressivos, anatomia simplificada, contornos escuros em degraus e blocos de pixels visíveis. Cabelo, barba e roupa têm menos detalhes finos para preservar a leitura em 96×96 e no jornal do celular. O busto em três quartos olha ligeiramente para a direita, com cabelo e ombros contidos na área transparente.

O rascunho do autor define Brás apenas como a primeira vítima. Pele clara, meia-idade avançada, cabelo grisalho penteado para trás, olhos azuis e barba branca curta são escolhas artísticas herdadas do retrato anterior, não atributos documentados na fonte. A sobrecasaca carvão, o colete escuro e a gravata marfim mantêm o traje de época, agora sem brocado ornamental. Sua expressão é altiva e discretamente sardônica; o retrato não representa o cadáver nem acrescenta pistas de autoria.

O PNG colorido de 1254×1254 mantém transparência verdadeira e é consumido pelo caminho público já utilizado em `renderJournal()`. O preto e branco é aplicado somente pela interface com `grayscale(1) contrast(1.25)` e a exibição continua com `image-rendering:pixelated`. Prompt completo, referências, arquivo de origem, revisão e hashes estão em [bras_cubas.json](../frontend/public/assets/portraits/bras_cubas.json); a entrada do [manifesto](../frontend/public/assets/portraits/manifest.json) preserva o ID `bras_cubas` e a escala lógica de 96×96.

Validação desta revisão: build TypeScript/Vite aprovado; PNG RGBA, transparência, margens visíveis e hash da cópia no build conferidos. O Brave carregou a nova imagem na primeira edição real do fluxo de teste, com filtro monocromático e renderização pixelada, em 1440×1000 e 390×844, sem transbordamento horizontal no celular. Comparação com Bentinho/Escobar e leitura em 96×96 inspecionadas. Capturas locais: `artifacts/bras-cubas-style-comparison.png`, `artifacts/bras-cubas-clarim-desktop.png` e `artifacts/bras-cubas-clarim-mobile.png`. A conferência usou armazenamento e respostas de teste, sem chamadas AWS.

## Contrato do manifesto e atlas

`characters/manifest.json` contém `{version, characters:[...]}`. Cada entrada possui:

- `id`, `type:"atlas"`, `path` e `atlasPath`.
- `sourceWidth` e `sourceHeight`: dimensões reais do PNG original.
- NPCs: `frameWidth:512`, `frameHeight:724`, seis frames, `idleFrames:["0","1"]`, `walkFrames:["2","3","4","5"]`, origem `{x:0.5,y:684/724}`.
- Floriano: `frameWidth:374`, `frameHeight:528`, dez frames, `idleFrames:["0","1"]`, `walkFrames:["2","3","4","5","6","7","8","9"]`, origem `{x:0.5,y:499/528}`.
- Esses tamanhos são o canvas **virtual não recortado** do atlas, não a divisão aritmética do PNG. A exibição continua `displayWidth:64`, `displayHeight:88`, com `portraitPath` para os NPCs.

Carregar com `scene.load.atlas(id, path, atlasPath)` e animar os nomes de frame como strings. **Não usar `load.spritesheet` com divisão uniforme para estas imagens.**

A IA entregou poses separadas, mas centros e largura de saias/pés não obedecem exatamente à grade uniforme. Cada atlas JSON contém retângulos medidos por inspeção do alfa e metadados de trim, sem modificar os pixels do PNG. Os campos `spriteSourceSize`/`sourceSize` alinham cabeça e pés em uma célula virtual comum. A base dos pés fica em684 nos NPCs e499 em Floriano; a origem correspondente evita que o padding faça o personagem flutuar acima do chão.

## Verificação e limites

Foram inspecionados visualmente os outputs e verificados dimensões, canal RGBA, transparência zero, seis regiões de personagem, retângulos contidos no PNG e em `sourceSize`, e baseline comum. Personagens possuem variação natural de braços/roupas entre poses; a animação é arte gerada, não motion capture. O ajuste fino de escala e legibilidade deve ser conferido no canvas do jogo durante integração.

Nenhum pixel foi desenhado ou retocado por script; o tratamento por código se limita à inspeção e aos JSON de empacotamento/manifesto. Imagens originais ficam preservadas e cópias finais estão versionadas no repositório.

## Revisão dos ambientes

Os cinco locais agora possuem duas artes opacas de 2048×768: `{id}-09h.png` e `{id}-18h.png`. Os quatro fundos originalmente diurnos e o cais originalmente ao entardecer foram preservados por cópia nos respectivos horários; as cinco contrapartes foram produzidas por **image_gen built-in**, alterando a iluminação e preservando os marcos, a câmera e o chão. O cais começa com céu azul e lampiões apagados, no mesmo horário dos outros locais. O manifesto registra os pares em `lighting.morning`/`lighting.sunset`; prompts completos, fontes e hashes ficam em [lighting-prompts.json](../frontend/public/assets/locations/lighting-prompts.json).

O relógio converte os 300 segundos de investigação em 09:00–18:00, usando o prazo confirmado pelo servidor. Os fundos mantêm a manhã até as 15h e fazem uma transição gradual para o pôr do sol até as 18h. Viagem e recarregamento preservam o horário; a assembleia pausa o tempo diurno e a iluminação. O ciclo e as verificações estão em [visuais_horario_caminhada.md](visuais_horario_caminhada.md).

Os cinco fundos foram simplificados por `image_gen built-in`, preservando os marcos e a composição de cada local. A tela passa a960×360, com câmera fixa. O atlas `frontend/public/assets/ambient/scene-life.png` reúne árvore, cão, gato, pássaro e dois cidadãos figurantes. O PNG tem transparência verdadeira; `scene-life.json` contém os retângulos medidos pelo alfa, sem editar os pixels. As caixas de exibição preservam as proporções dos recortes. Os figurantes não são suspeitos ou agentes de investigação. Prompts completos, modo de geração, fontes, dimensões e hashes estão em [prompts.json](../frontend/public/assets/ambient/prompts.json). Os PNGs dos fundos estão em `frontend/public/assets/locations/`; os originais permanecem no histórico Git.

## Linha de chão, jornal e vestígios

Os personagens usam a origem do manifesto (`y=684/724` nos NPCs e `y=499/528` em Floriano) e ficam na coordenada `ground_y` da localização. A roda de capoeira usa baseline virtual `480/512`, fica à direita diante do poste e foi avançada 20 px para o passeio em primeiro plano (`ground_y + 20`), colocando os pés dos músicos no calçamento à frente da mureta. Os dois capoeiristas usam lenços no pescoço, sem cordas na cintura. A árvore decorativa em x=100 foi retirada, e a árvore em primeiro plano do fundo foi removida por image_gen, deixando o poste esquerdo do cais livre. A edição do fundo está registrada em `assets/locations/cais-lanternas-edit.json`; o prompt atualizado da roda está em `assets/ambient/capoeira-prompts.json`.

O Clarim abre como uma página de jornal em preto e branco: textura e moldura de papel impresso, masthead com filetes duplos, dateline, manchete tipográfica, relato, localização e botão no estilo de tinta. A imagem monocromática `assets/press/crime-scene-snapshot.png` representa o registro jornalístico do acontecimento sem identificar culpado ou vítima. O arquivo é uma ilustração de arquivo compartilhada entre edições, não uma fotografia dinâmica específica de cada crime; título, relato e local são os dados reais da edição. Prompt, fonte e hash ficam em `assets/press/snapshot-prompts.json`.

Os vinte apetrechos do catálogo têm símbolos vetoriais próprios em `assets/items/item-icons.svg`, indexados por `item_id` no [manifesto](../frontend/public/assets/items/manifest.json). A interface mostra o mesmo objeto no caderno, ao selecionar a apresentação para um NPC, nos depoimentos e nas provas da acusação. Os traços geométricos usam contornos e cores de papel, latão, couro, vinho e verde do jogo; a distinção entre exclusivo, singular e comum também aparece na moldura do cartão.
