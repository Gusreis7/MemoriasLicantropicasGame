# Locais e mapa — assets visuais

Branch da frente: `feat/assets_locais_mapa`. Os seis assets finais foram gerados com **image_gen built-in**, inspecionados visualmente e copiados para esta worktree. Não são SVGs procedurais nem placeholders.

Fonte narrativa consultada somente para leitura: `/home/gustavoreis/Documentos/QuemEOLobisomem/Locais`. Praça Verde, Cabana da Capitu e Casa Verde vêm desses rascunhos; Café do Largo e Cais das Lanternas são os dois locais ficcionais novos aprovados no plano.

## Direção de arte

Pixel art detalhada com agrupamentos visíveis de pixels, fachadas coloniais, telhados de barro, vegetação tropical e materiais de madeira/pedra. Paleta compartilhada de ocre, terracota, verde-sálvia, verde-garrafa, luz âmbar e azuis discretos ao fundo. A cena do cais varia para o entardecer, mantendo os mesmos materiais e tratamento de pixels.

As cinco cenas usam câmera lateral à altura de um pedestre. A praça, a casa e a cabana têm trechos de cenário visíveis em profundidade, mas a faixa de movimento é horizontal. Nenhuma cena inclui personagem, NPC, animal, texto, UI ou sinal visual associado ao papel de lobisomem.

## Entregas e dimensão real

| ID | Arquivo final | Dimensão PNG |
| --- | --- | --- |
| `praca_verde` | `frontend/public/assets/locations/praca_verde.png` | 2172×724 |
| `cabana_capitu` | `frontend/public/assets/locations/cabana_capitu.png` | 2172×724 |
| `casa_verde` | `frontend/public/assets/locations/casa_verde.png` | 2172×724 |
| `cafe_largo` | `frontend/public/assets/locations/cafe_largo.png` | 2172×724 |
| `cais_lanternas` | `frontend/public/assets/locations/cais_lanternas.png` | 2172×724 |
| `city` | `frontend/public/assets/map/city.png` | 1536×1024 |

Manifestos: `assets/locations/manifest.json` e `assets/map/manifest.json`. Registram caminhos públicos, dimensões reais, dimensões lógicas propostas, gerador, arquivo de origem e hash SHA-256. As imagens são backgrounds opacos: transparência não é necessária para estes assets.

## Briefs dos locais

**Praça Verde:** praça arborizada com bancos de ferro, coreto, quiosque de jornal, calçamento e fachadas ao fundo. É o hub inicial. A fachada e o desenho do coreto ajudam a identificar o local mesmo sem rótulos. Player inicia em x160 e Rubião em x440, conforme contrato; essas posições são definidas pelo backend, não embutidas na imagem.

**Cabana da Capitu:** casa térrea de madeira e alvenaria, varanda sombreada, plantas e mesa de atendimento visível. O espaço é íntimo e acolhedor. Cartas, livro e pequenas velas são detalhes do trabalho, sem transformar a personagem em caricatura ameaçadora. Capitu e Virgília são sprites separados, em x440 e x900 conforme contrato.

**Casa Verde:** instituição colonial verde, fachada austera com janelas altas, portão e pequeno jardim. Há recepção visível e detalhes científicos discretos, sem tecnologia moderna ou pacientes desenhados na imagem. Bacamarte ocupa x460 pelo estado de mundo.

**Café do Largo:** esquina de convivência, toldo vinho, mesas e balcão visível, plantas e iluminação quente. As mesas ficam atrás da faixa de movimento, permitindo que o jogador caminhe à frente. Bentinho e Escobar ocupam x460 e x900; isso não implica conversa ou aliança nova no roteiro.

**Cais das Lanternas:** passeio junto à água, barcos à vela, cordas, armazém e lanternas a gás no entardecer. Materiais de pedra e madeira, com contraste entre água azul e luz âmbar. Caixas e amarras ficam atrás do caminho frontal. Florença aparece como sprite em x480, sem introduzir testemunho, pista ou evento novo.

## Enquadramento e integração

Contrato do mundo: largura1920, altura360, chão lógico em y300 e câmera640×360. As imagens geradas são panoramas3:1. O frontend deve escolher conscientemente o enquadramento/escala para a área lógica1920×360, sem tratar as dimensões do PNG como coordenadas do servidor. Redimensionar diretamente para esse retângulo comprime verticalmente a arte; enquadramento com proporção preservada é alternativa quando houver camadas/letterboxing apropriados.

Todas as cenas têm uma faixa frontal pavimentada livre que inclui a linha lógica y300 quando ajustadas ao retângulo do mundo. O piso amplo permite sobrepor os sprites; grades, portas, mesas e árvores são cenografia atrás da faixa de caminhada. As colisões e os limites continuam sendo dados do catálogo de mundo. Estas imagens não são tilemaps nem contêm colisões extraídas automaticamente dos pixels.

Os seis arquivos foram preservados na resolução nativa, sem desenhar substitutos ou fazer edições visuais via Python. A verificação de cabeçalho/dimensões e hashes usa somente leitura binária dos PNGs.

## Mapa

O mapa é um bairro ficcional ilustrado, com cinco marcos reconhecíveis e caminhos entre eles. Não pretende representar a geografia real do Rio de Janeiro. Os rótulos e botões são responsabilidade da interface, não texto dentro da imagem.

Hotspots normalizados sugeridos no manifesto (x/y entre0e1):

| Local | x | y |
| --- | --- | --- |
| Cabana da Capitu | 0.19 | 0.31 |
| Casa Verde | 0.81 | 0.37 |
| Praça Verde | 0.50 | 0.55 |
| Café do Largo | 0.19 | 0.75 |
| Cais das Lanternas | 0.82 | 0.80 |

São âncoras de apresentação, não regras de proximidade. A viagem usa IDs de local e spawn definido pelo backend. O mapa não mostra a identidade do lobisomem.

## Prompts e proveniência

O conjunto final de prompts está em `frontend/public/assets/locations/prompts.json`. Cada asset distinto teve sua própria chamada ao `image_gen` built-in; nenhuma chave de API foi usada pelo código do repositório. Não foram usados assets de terceiros nem arquivos gráficos de Stardew Valley.

As saídas originais permaneceram em `/home/gustavoreis/.codex/generated_images/01a198c6-4b52-7852-a3b0-94d7028ce416/`. Os manifestos conservam os nomes de origem para rastreio, mas a aplicação só referencia cópias versionadas dentro de `frontend/public/assets/`.

Inspeção realizada: ausência de personagens/texto/UI, continuidade da faixa frontal, identidade arquitetônica dos cinco locais, legibilidade dos marcos do mapa, consistência da paleta e dimensões de cada PNG. Testes de renderização/navegador e integração com sprites pertencem à frente de frontend/coordenação.
