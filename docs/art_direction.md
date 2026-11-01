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

Oito sheets PNG RGBA foram geradas com seis poses cada: duas de idle e quatro de caminhada. As figuras ficam voltadas para a direita; espelhar horizontalmente fornece a direção esquerda. Na exploração atual os NPCs usam uma pose fixa de repouso para evitar variações de silhueta; o jogador usa os quatro frames ao caminhar.

Os retratos reutilizam a respectiva sheet como referência de identidade. Olhos dourados de Capitu, verdes de Escobar e âmbar de Florença são legíveis no retrato. Não foi criado retrato de Brás Cubas ou do jogador, pois o diálogo exibe a persona abordada.

## Contrato do manifesto e atlas

`characters/manifest.json` contém `{version, characters:[...]}`. Cada entrada possui:

- `id`, `type:"atlas"`, `path` e `atlasPath`.
- `sourceWidth` e `sourceHeight`: dimensões reais do PNG original.
- `frameWidth:512`, `frameHeight:724`: tamanho **virtual não recortado** do frame no atlas, não divisão aritmética do PNG.
- `frames:6`, `frameNames:["0","1","2","3","4","5"]`, `idleFrames:["0","1"]`, `walkFrames:["2","3","4","5"]`.
- `displayWidth:64`, `displayHeight:88`, `origin:{x:0.5,y:684/724}` e `portraitPath` para os NPCs.

Carregar com `scene.load.atlas(id, path, atlasPath)` e animar os nomes de frame como strings. **Não usar `load.spritesheet` com divisão uniforme para estas imagens.**

A IA entregou seis poses separadas, mas centros e largura de saias/pés não obedecem exatamente à grade uniforme. Cada atlas JSON contém retângulos medidos por inspeção do alfa e metadados de trim, sem modificar os pixels do PNG. Os campos `spriteSourceSize`/`sourceSize` alinham cabeça e pés em uma célula virtual comum. Todos os frames têm a base dos pés em684; a origem correspondente evita que o padding faça o personagem flutuar acima do chão.

## Verificação e limites

Foram inspecionados visualmente os outputs e verificados dimensões, canal RGBA, transparência zero, seis regiões de personagem, retângulos contidos no PNG e em `sourceSize`, e baseline comum. Personagens possuem variação natural de braços/roupas entre poses; a animação é arte gerada, não motion capture. O ajuste fino de escala e legibilidade deve ser conferido no canvas do jogo durante integração.

Nenhum pixel foi desenhado ou retocado por script; o tratamento por código se limita à inspeção e aos JSON de empacotamento/manifesto. Imagens originais ficam preservadas e cópias finais estão versionadas no repositório.

## Revisão dos ambientes

Os cinco fundos foram simplificados por `image_gen built-in`, preservando os marcos e a composição de cada local. A tela passa a960×360, com câmera fixa. O atlas `frontend/public/assets/ambient/scene-life.png` reúne árvore, cão, gato, pássaro e dois cidadãos figurantes. O PNG tem transparência verdadeira; `scene-life.json` contém os retângulos medidos pelo alfa, sem editar os pixels. As caixas de exibição preservam as proporções dos recortes. Os figurantes não são suspeitos ou agentes de investigação. Prompts completos, modo de geração, fontes, dimensões e hashes estão em [prompts.json](../frontend/public/assets/ambient/prompts.json). Os PNGs dos fundos estão em `frontend/public/assets/locations/`; os originais permanecem no histórico Git.

## Linha de chão, jornal e vestígios

Os personagens usam a origem `y=684/724` do manifesto e ficam na coordenada `ground_y` da localização. A roda de capoeira usa baseline virtual `480/512`, fica à direita diante do poste e foi avançada 20 px para o passeio em primeiro plano (`ground_y + 20`), colocando os pés dos músicos no calçamento à frente da mureta. Os dois capoeiristas usam lenços no pescoço, sem cordas na cintura. A árvore decorativa em x=100 foi retirada, e a árvore em primeiro plano do fundo foi removida por image_gen, deixando o poste esquerdo do cais livre. A edição do fundo está registrada em `assets/locations/cais-lanternas-edit.json`; o prompt atualizado da roda está em `assets/ambient/capoeira-prompts.json`.

O Clarim abre como uma página de jornal em preto e branco: textura e moldura de papel impresso, masthead com filetes duplos, dateline, manchete tipográfica, relato, localização e botão no estilo de tinta. A imagem monocromática `assets/press/crime-scene-snapshot.png` representa o registro jornalístico do acontecimento sem identificar culpado ou vítima. O arquivo é uma ilustração de arquivo compartilhada entre edições, não uma fotografia dinâmica específica de cada crime; título, relato e local são os dados reais da edição. Prompt, fonte e hash ficam em `assets/press/snapshot-prompts.json`.

Os vinte apetrechos do catálogo têm símbolos vetoriais próprios em `assets/items/item-icons.svg`, indexados por `item_id` no [manifesto](../frontend/public/assets/items/manifest.json). A interface mostra o mesmo objeto no caderno, ao selecionar a apresentação para um NPC, nos depoimentos e nas provas da acusação. Os traços geométricos usam contornos e cores de papel, latão, couro, vinho e verde do jogo; a distinção entre exclusivo, singular e comum também aparece na moldura do cartão.
