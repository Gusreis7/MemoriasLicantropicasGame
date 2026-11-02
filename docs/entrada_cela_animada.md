# Entrada animada na cela

Branch: `feat/entrada_cela_animada`, integrada em `develop` após validação.

Uma nova detenção confirmada pelo servidor apresenta a grade aberta. A pessoa caminha pelo corredor em primeiro plano, entra pela abertura central, para dentro da cela e aguarda o fechamento da grade. A sequência dura cerca de 2,25 segundos: 900ms pelo corredor, 650ms para entrar e 600ms para a grade fechar. Legendas anunciam entrada, fechamento e espera.

A grade é desenhada somente dentro da abertura central: ao deslizar, desaparece atrás da parede, preservando a visibilidade dos bancos e do arquivo à direita.

São usados o sprite e os frames de caminhada do personagem efetivamente detido, tanto masculino quanto feminino. O cenário e os assets existentes são preservados. Retomar uma partida com alguém já sob custódia mostra diretamente a pessoa na cela fechada; a consulta periódica do estado não reinicia a animação. Uma nova detenção da mesma pessoa em outro dia pode reproduzir a entrada novamente.

Noite, transformação e soltura interrompem qualquer animação anterior, cancelam seus temporizadores e restauram a posição correta antes de iniciar a próxima apresentação. A destruição da cena também cancela os temporizadores. A preferência de movimento reduzido apresenta diretamente a cela fechada.

A apresentação não altera o relógio, o resultado da acusação ou o estado da partida. O jogador pode voltar à investigação durante o dia usando o botão existente.

## Validação

Build TypeScript/Vite e 42 testes frontend aprovados. Oito fluxos afetados foram aprovados no Brave: detenção, transformação, soltura, entrada de Rubião e Florença, ausência de repetição durante consultas, retomada de caso e movimento reduzido. Os testes usam Redis temporário e LLM determinístico, sem chamadas AWS ou alterações nos dados das partidas de desenvolvimento.

Após o acabamento do recorte, os fluxos de entrada e soltura foram revalidados. Uma comparação de pixels confirma que a região dos bancos e do arquivo permanece igual antes e depois do fechamento. Capturas da entrada e da cela fechada foram inspecionadas. Docker atualizado e conferido no Brave nas portas7077 e7078.
