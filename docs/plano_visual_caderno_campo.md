# Plano visual: caderno de campo de Floriano

## Diagnóstico

- O diálogo já contém um spread de duas páginas, mas o CSS distribui o espaço em `0.76fr / 1.55fr`, deixando a página dos suspeitos com cerca de um terço da largura.
- A dobra visual está posicionada em `32.97%`, reforçando a divisão desigual.
- O redesenho anterior adicionou `backdrop-filter`, gradientes de brilho e `perspective/rotateY` nas folhas. Esses efeitos reduzem a nitidez percebida do pixel art e da tipografia.
- O título “Caderno de suspeitos” e os controles de abas fazem a janela parecer um menu. A estrutura precisa ler como o caderno pessoal de Floriano aberto sobre uma mesa.
- Os dados, retratos, itens, X dos mortos, relatos, abas e atalhos já funcionam e devem permanecer.

## Direção visual e efeitos

1. Dividir o livro em duas páginas de mesma largura (`1fr / 1fr`), com a dobra no centro geométrico do spread. Em telas estreitas as folhas continuam empilhadas para caber na viewport.
2. Usar uma capa de couro simples, lombada central e sombra firme abaixo do objeto. Evitar desfoque, transparência em cima do conteúdo e transformações 3D que interpolam retratos e texto.
3. Mostrar bordas de várias folhas por trás do spread e pequenas marcas coloridas indexando “Moradores”, “Pistas” e “Relatos”. As marcas ficam atrás das páginas, sem cobrir ou capturar interação.
4. Apresentar a janela como “Caderno de campo” / “Anotações de Floriano”. Remover o cabeçalho que a nomeia como menu de suspeitos. Manter rótulos de página e seção como notas editoriais dentro do livro.
5. Manter pixel art e tipografia sem filtros de suavização. Retratos permanecem pixelados; o X vermelho comunica morte; o conteúdo mantém contraste e leitura.

## Contrato entre frentes

| Frente | Branch | Arquivos exclusivos | Entrega |
| --- | --- | --- | --- |
| Estrutura editorial | `fix/notebook-agenda-structure` | `frontend/game/main.ts` | Título de caderno de campo, invólucro do spread e marcações decorativas de página; preservar todos os IDs, dados, abas e atalhos atuais. |
| Livro físico e nitidez | `fix/notebook-spread-physical` | `frontend/game/style.css` | Duas metades iguais, dobra em 50%, folhas em camadas e abas atrás; remover efeitos que suavizam ou interpolam o conteúdo. Preservar layout responsivo e estilos dos controles existentes. |

## Integração e aceite

- As frentes não editam os mesmos arquivos e partem do `develop` com este contrato.
- O caderno aberto deve mostrar duas páginas equivalentes, a lombada centrada e marcadores saindo das folhas de trás.
- Não deve haver blur, brilho radial sobre o papel, `backdrop-filter` nem rotação 3D nos elementos do caderno.
- Confirmar que os seletores, conteúdos, marcas de falecimento, atalhos e rolagem ainda existem.
- Reconstruir a aplicação e revisar a tela no Brave após a integração. Não executar a suíte de testes nesta entrega.
