# Iluminação à meia-noite

Os cinco locais têm uma terceira arte opaca de 2048×768 em `frontend/public/assets/locations/{id}-00h.png`, com lua cheia visível, luz azul-prata no chão, vegetação e telhados, e luz âmbar das lâmpadas existentes. Câmera, marcos e linha de chão preservam os fundos diurnos. Todas foram geradas separadamente por edição com **image_gen built-in** e inspecionadas visualmente; não houve retoque de pixels por script.

`locationLighting(id).midnight` fornece chave de textura e caminho. O manifesto registra `lighting.midnight` com horário `00:00`, dimensões e hash. A cena e a sequência de ataque consomem essa camada no período noturno. Prompts completos, referências e fontes estão em [midnight-prompts.json](../frontend/public/assets/locations/midnight-prompts.json).

O teste de iluminação verifica os três horários para cada local, existência PNG, dimensões e correspondência com o manifesto. As artes mantêm a proporção 8:3 da área de jogo 960×360.
