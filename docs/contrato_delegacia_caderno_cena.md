# Contrato visual: delegado, caderno e cenas de crime

## Escopo dividido

| Branch | Arquivos próprios | Entrega |
| --- | --- | --- |
| `feat/delegado_frente` | `frontend/game/custody.ts` | Avatar completo do delegado em primeiro plano, em escala legível e apoiado visualmente no chão/cadeira, alinhado à mesa sem parecer encolhido nem ficar atrás do móvel. |
| `feat/caderno_fisico` | `frontend/game/main.ts`, `frontend/game/style.css` | Dar ao spread existente aparência de objeto físico: capa/lombada, folhas com volume, dobra, costura e sombras. Preservar cartões, suspeitos, X de mortos, abas e atalhos. |
| `feat/policiais_aviso_cena` | `frontend/game/scene.ts`, novos assets sob `frontend/public/assets/crime-scene/` e seu manifesto/prompt | Colocar policiais de época e aviso `CENA DO CRIME · NÃO ULTRAPASSE` perto de cenas investigáveis. O aviso deve ter texto exato e legível; polícia e fita são cenografia estática. |

## Contratos de integração

- As três branches partem de `develop` e não alteram arquivos fora dos seus escopos.
- Delegado fica em primeiro plano, dimensionado como figura adulta da cena 960×540, com os pés/cadeira sobre o chão e sem ser ocultado por uma camada de mesa que o faça parecer sentado atrás dela.
- A cena do crime desenha policiais e aviso somente quando houver crimes com vestígios restantes no local atual. Estes elementos não são suspeitos, não se movem, não são selecionáveis e não alteram busca, posições de pistas ou navegação.
- Se houver vários crimes no mesmo ponto, exibir uma única composição de polícia/aviso para aquele ponto e manter o contador atual de cenas/vestígios.
- Texto do aviso é renderizado em código com caracteres exatos; asset raster não deve conter texto gerado.
- O caderno mantém DOM, IDs, abas, retratos, pilhas, status de morte e atalhos que já existem; o trabalho desta branch muda a materialidade visual do livro.
- O agente de integração revisa os três commits, reconstrói/reinicia Docker e confirma saúde HTTP. Não executar a suíte de testes nesta entrega.
