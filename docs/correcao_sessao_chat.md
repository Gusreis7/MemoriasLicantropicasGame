# Correção da disponibilidade do chat

A partida afetada abriu a conversa com Rubião às03:02:07UTC. O evento social de03:02:51UTC reservou Rubião para outro encontro e o levou da Praça Verde ao Cais. O chat continuou aberto; novas perguntas retornavam403 por local/distância, enquanto a leitura do histórico retornava200. O handler escondia os motivos seguros de disponibilidade sob “Acesso não permitido”, e o frontend tratava a rejeição explícita como uma possível resposta perdida, mantendo novos envios habilitados.

A abordagem agora grava uma reserva de presença por NPC, renovável e limitada a90 segundos ou ao anoitecer. A agenda social exclui o NPC enquanto essa reserva estiver válida. O navegador renova a abordagem a cada15 segundos durante um diálogo ativo, sem inferência, e libera a reserva ao fechar. Abandono da aba ou falha de fechamento se recupera pelo prazo. A reserva curta da ação continua protegendo inferência e persistência; não se mantém uma transação Redis aberta enquanto o jogador lê.

Ausência, deslocamento, distância e custódia têm códigos e textos públicos restritos, sem expor mensagens internas de exceção. Uma rejeição403/404 deixa o formulário indisponível até nova abordagem, conserva o rascunho e não dispara tentativa automática nem busca de uma resposta que o servidor não aceitou. Falhas de rede continuam usando o fluxo de confirmação pelo histórico. Históricos de NPCs mortos continuam consultáveis pelos participantes autorizados, sem permitir novas perguntas a eles.

A correção preserva regras de noite, alcance, morte e custódia. Não permite conversar remotamente com um NPC que já saiu: é necessário fechar a conversa e abordá-lo novamente onde estiver. O rascunho fica associado à partida e à conversa.

Regressões verificam reserva, renovação, exclusão da agenda, liberação, expiração, erro HTTP específico sem chamar o modelo, consulta de histórico após morte e recuperação de rascunho. O reinício do Compose usa o overlay AWS local e preserva o volume Redis, as partidas e as transcrições.

Validação:527 testes Python com armazenamento em memória,54 testes direcionados com Redis real,40 testes frontend e três fluxos Brave aprovados. Após `docker compose down` e `up --wait` com overlay AWS, os quatro serviços ficaram saudáveis. Duas perguntas consecutivas ao Qwen real foram respondidas e persistidas no Brave; fechar e reabrir a conversa recuperou ambas. Captura local em `artifacts/chat-fixed-real.png`. A partida afetada e os históricos não foram apagados.
