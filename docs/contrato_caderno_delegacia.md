# Contrato: caderno de Floriano e delegado na cela

## Plano visual

- O caderno abre como um volume de duas páginas, com lombada central, papel de arquivo e tipografia editorial legível.
- Página esquerda: retratos e nomes dos suspeitos, estado vivo/falecido e marca de morte em X vermelho pixelado sobre o retrato.
- Página direita: abas `Pistas` e `Relatos`. Pistas agrupam vestígios, depoimentos, álibis, confrontos e cenas; Relatos reúne as fofocas ouvidas e suas fontes.
- Em telas estreitas, as páginas empilham sem perder cabeçalho, abas ou navegação por teclado.
- Atalhos: `C` abre/fecha o caderno quando nenhum campo de texto ou modal incompatível estiver ativo; `1` abre Pistas e `2` abre Relatos enquanto o caderno estiver aberto; `Esc` fecha o caderno.
- As mortes são lidas do estado público dos personagens (`alive`). O X é desenho vetorial em degraus pixelados e não altera o retrato-fonte.
- Na cela, o delegado usa o sprite sentado existente, ampliado e alinhado com cadeira e mesa no fundo; não usar o retrato da interface.

## Contratos de trabalho e integração

| Frente | Arquivos próprios | Contrato |
| --- | --- | --- |
| Cela | `frontend/game/custody.ts` | Ajustar recorte, escala, posição e profundidade do sprite completo sentado; mantê-lo dentro da cadeira/mesa e visível em todos os estados da custódia. |
| Caderno | `frontend/game/main.ts`, `frontend/game/style.css` | Implementar spread, retratos com X para mortos, abas, conteúdo existente e atalhos sem mudar regras/API do jogo. |
| Integração | `docs/contrato_caderno_delegacia.md` e branch `develop` | Revisar os dois commits, integrar as branches, compilar e reiniciar Docker. |

Branches de feature derivam de `develop` e cada frente altera apenas seus arquivos próprios. O agente do caderno não edita a cena da cela; o agente da cela não altera o caderno. A integração final valida os seletores já usados em `main.ts` e mantém o ciclo de jogo intacto.
