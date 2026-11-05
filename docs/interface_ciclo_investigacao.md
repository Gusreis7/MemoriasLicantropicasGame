# Interface do ciclo de investigação

A branch `feat/interface_investigacao` apresenta o ciclo definido em [contratos_ciclo_investigacao.md](contratos_ciclo_investigacao.md). O navegador recebe somente `CasePublic`: não contém inventários particulares, donos reais dos vestígios, veracidade dos depoimentos ou papel secreto antes do desfecho.

## Relógio, noite e manhã

O relógio exibe a diferença entre `phase_ends_at` e `server_time`, limitada por `seconds_remaining`, descontando o tempo monotônico desde a resposta. O relógio do computador não decide o período. Quando a contagem acaba, a exploração fica bloqueada até a confirmação do servidor; o cliente nunca cria uma vítima ou avança um dia.

O polling executa uma requisição por vez e agenda a seguinte após a conclusão. Respostas de outra partida ou com revisão menor são descartadas. Noite e fim de partida bloqueiam mapa, caminhada, abordagem, buscas, apresentação e acusação. Escape não fecha a espera noturna, cujo foco fica contido. O relógio continua enquanto se lê um jornal, caderno ou conversa.

A transição aguarda intenções de movimento pendentes antes de aceitar o novo mundo. O amanhecer recarrega mundo e elenco, posiciona Floriano pela coordenada recebida e abre o jornal. Se a leitura falhar, os controles ficam bloqueados e a próxima sincronização tenta novamente. A noite encerra a interação com o diálogo; uma resposta tardia não devolve foco ao campo escondido.

O Clarim abre no início e a cada manhã. Seu botão permanece no toolbar. A Praça mostra a marca da banca em x160, posição acordada para o amanhecer. O desfecho apresenta a mensagem do motor e permite iniciar outro caso.

## Caderno, cenas e delegado

As cenas públicas com vestígios restantes recebem uma marca no chão. “Procurar vestígios” aparece na mesma localização, a90px ou menos; E prioriza essa busca quando disponível. O servidor revalida a posição. O caderno recebe o objeto retornado, sem o cliente escolher tipo ou proprietário.

Dentro da conversa há seleção de vestígio recolhido e apresentação ao NPC próximo. A resposta registrada aparece junto aos controles e no caderno, associada à testemunha e ao objeto. A interface não transforma negação, reconhecimento ou desconhecimento em verdade comprovada.

O formulário do delegado envia apenas suspeito e IDs dos vestígios/depoimentos escolhidos. Exibe aceitação ou recusa e a justificativa pública, e impede outra tentativa no mesmo dia. Transformação e vitória dependem da resolução do servidor.

A cena compara a composição dos NPCs mesmo sem trocar de localização, removendo vítimas do snapshot sem recriar o fundo por passo. A roda de capoeira aparece somente no Cais, ao fundo, com quatro frames e pose fixa quando `prefers-reduced-motion` está ativo; não participa do elenco ou das ações investigativas.

## Verificação

- Build TypeScript/Vite e27 testes Vitest: relógio, bloqueio, proximidade, polling sequencial e contratos HTTP, além dos anteriores.
- Dois fluxos Playwright no **Brave instalado**, com API simulada conforme o contrato: busca, apresentação, caderno, acusação, noite e vitória; e amanhecer, jornal e atualização do elenco. Sem AWS.
- A coordenação valida backend/Redis, relógio controlado e Docker. Os fluxos anteriores precisam ler o jornal inicial (`#read-journal`) antes de caminhar.

O botão **Pular o dia**, na barra de investigação, avança diretamente até a manhã seguinte e abre o Clarim. Aguarda movimentos pendentes e atualiza mundo e elenco pela resposta do servidor. Fica desabilitado durante ações, janelas abertas, assembleia, noite ou fim de partida; falhas permitem nova tentativa sem avançar o relógio local.
