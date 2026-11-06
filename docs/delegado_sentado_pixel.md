# Delegado sentado — revisão de estilo

Revisão 3: a pedido do autor, a simplificação recebeu um aumento moderado de detalhe. O rosto e o bigode ganharam mais planos de luz, os dedos têm articulações legíveis, lapelas e botões têm acabamento, e calçados e madeira recuperaram definição. A identidade, pose, proporções expressivas e contornos pixelados foram preservados, sem retornar ao realismo da primeira versão. Fonte: `exec-9064c50f-982d-448d-baee-cfdfdd9e1503.png`; SHA256 `3ea604381c6e9ab5029cddcbd0d446db572ad1ed53b4eeaea0ab80822ccf2fcf`.

O asset `assets/custody/delegado-sentado.png` foi redesenhado com image_gen built-in usando Floriano como referência principal de proporção e pixel art, e o retrato revisado de Brás Cubas como referência de simplificação facial. O delegado conserva pele morena, cabelo grisalho penteado para trás, bigode, expressão séria, sobrecasaca carvão, colete castanho e cadeira de madeira.

A cabeça e os olhos têm leitura mais expressiva, as mãos e dobras foram simplificadas e as sombras usam blocos maiores de pixels. O PNG RGBA de 1024×1536 substitui o caminho já carregado por `CustodyScene`, mantendo apresentação em 150×225 e origem nos pés. Nenhum código de fluxo foi alterado.

Prompts completos, referências e fontes estão em [delegado-sentado.json](../frontend/public/assets/custody/delegado-sentado.json). Os pixels e o alfa gerados foram preservados; permanece uma franja ambiente semitransparente discreta no output, sem fundo opaco. A transparência e a composição foram inspecionadas, e o build TypeScript/Vite foi aprovado.
