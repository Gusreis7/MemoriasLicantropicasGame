# Jogo no navegador

Implementado na frente `feat/jogo_exploracao`. O jogo usa Phaser 4 para o mundo lateral e HTML/CSS para interface, mapa e conversa. Nenhuma informação de papel secreto é utilizada pelo cliente.

## Fluxo

1. A tela inicial cria uma partida ou recupera o UUID salvo em `localStorage`.
2. Carrega snapshot público, catálogo dos cinco locais e manifesto real de personagens.
3. Carrega atlas com `load.atlas`, usando os retângulos e os pivôs gerados pela frente de arte. Não presume que o PNG possui uma grade uniforme.
4. Renderiza o cenário a 640×360 lógicos, com câmera lateral e chão na altura definida pelo backend.
5. `A/D` e setas movem, `E` aborda e `M` abre o mapa. Nome e retrato do interlocutor acompanham o diálogo.
6. Viagem usa o servidor para determinar o spawn. O histórico é recuperado novamente em cada abordagem, permitindo retomar o mesmo encontro.

O ID salvo não é uma credencial de autenticação. A aplicação continua sendo um protótipo local de um jogador, conforme o contrato do backend.

## Movimento

O cliente prevê a caminhada a 210 pixels lógicos/s, limita a posição à área pública e envia comandos em intervalos de 150ms ou na troca de direção. Existe no máximo uma requisição de movimento em andamento. A parada é confirmada antes de abrir diálogo ou mapa, evitando disputar a reserva de jogador.

Cada comando usa a última revisão e sequência confirmadas. Um conflito 409 recupera o snapshot público, sem reenviar automaticamente o comando antigo. A viagem conserva a sequência devolvida pelo servidor. Nenhum movimento, mapa ou animação chama o LLM.

## Diálogo

Durante a conversa, o teclado global do Phaser fica desativado para não consumir letras ou atalhos do campo de texto. O servidor fixa o remetente como jogador. O frontend envia somente `npc_id` na abordagem e `content` ao conversar, nunca papéis ou IDs arbitrários de remetente.

As falas são inseridas no DOM com `textContent`, sem interpretar HTML gerado pelo modelo. Durante a inferência, enviar/fechar ficam suspensos. Em erro, a interface consulta o histórico e não repete automaticamente a mensagem. As janelas têm `role=dialog`, foco preso e fechamento por Esc quando seguro.

## Verificação

Os testes unitários em `game/*.test.ts` verificam contratos HTTP, ausência de retry no envio, limites, alcance, sequência após viagem e comandos concorrentes. A coordenação executa o build completo e a inspeção no navegador após integrar a entrada admin e os assets.

Referências primárias usadas: [câmera Phaser](https://docs.phaser.io/phaser/concepts/cameras) e [scale manager](https://docs.phaser.io/phaser/concepts/scale-manager).
