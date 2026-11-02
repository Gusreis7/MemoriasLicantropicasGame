# Janela do delegado

O pedido de prisão apresenta o delegado em um painel verde com retrato pixel art e o caso em uma página de papel. O fluxo contém três passos: escolher o suspeito, selecionar vestígios e selecionar depoimentos. Cada suspeito aparece com seu retrato e nome; mortos e detidos continuam identificáveis, com estado explícito e seleção bloqueada. A escolha é obrigatória e pode ser feita com teclado. Depoimentos também mostram o retrato de quem falou.

Em telas menores, o delegado ocupa um cabeçalho compacto e o formulário fica em uma coluna, com rolagem para alcançar as provas e a confirmação. A seleção permanece ao fechar e reabrir a janela. O formulário envia o mesmo contrato de acusação: IDs do suspeito e dos registros selecionados.

## Arte

- Retrato: `frontend/public/assets/portraits/delegado.png`, PNG transparente de1254×1254, produzido por **image_gen built-in**.
- Prompt completo, referência e proveniência: [delegado.json](../frontend/public/assets/portraits/delegado.json).
- Referência de estilo: retrato existente de Bacamarte, usado apenas para orientar pixel art, cores e contornos. O delegado é um personagem visual de apoio e não faz parte do elenco sorteado.
- Os sete retratos dos suspeitos são os assets existentes, resolvidos pelo manifesto de personagens.

## Verificação

Build TypeScript/Vite e39 testes frontend aprovados. O fluxo Brave cobre seleção de suspeito e envio dos IDs corretos; a revisão da janela verifica teclado, estados indisponíveis, carregamento de imagens e ausência de rolagem horizontal em390px. Capturas locais em `artifacts/delegate-desktop.png` e `artifacts/delegate-mobile.png`.

Quatro fluxos de investigação no Brave aprovados. O fluxo de álibi foi repetido após ser interrompido pelo recarregamento automático do Vite durante uma edição; a repetição passou. O build Docker atualiza jogo e admin, preservando a API e o volume Redis.
