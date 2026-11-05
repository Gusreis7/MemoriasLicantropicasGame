# Ataque noturno

O canvas noturno reproduz apenas uma morte nova confirmada na edição pública do servidor. Como o servidor só divulga a vítima ao resolver a noite, a apresentação mantém a espera noturna até essa resposta, encena o ataque e só depois abre o Clarim. Não consulta dados privados nem antecipa a vítima ou a identidade humana do lobisomem. Recarregar um caso já resolvido não repete mortes antigas.

O cenário usa a arte de meia-noite do local confirmado da vítima mesmo que Floriano esteja em outro bairro. A câmera abre em 960×360. O lobisomem usa o atlas feral existente, chega agachado e golpeia; a vítima tomba nas sombras sem sangue. As quatro variações ciclam entre garra lateral, golpe descendente, bote rasteiro e salto de emboscada. A escuridão cresce durante a aproximação; NPCs públicos presentes e figurantes recebem blur e rastros horizontais. A vítima e o monstro permanecem em foco.

O botão Pular animação e Escape encerram a sequência; movimento reduzido pula diretamente ao relato. Nova investigação cancela carregamentos/animação, e imagens indisponíveis têm prazo máximo de oito segundos antes de liberar o jornal. O cenário normal também carrega a placa 00h enquanto a fase pública é noturna.

Verificação: `night-attack.test.ts` confere quatro golpes e deduplicação das mortes. O teste E2E de amanhecer em `investigation.spec.ts` exige a animação antes do jornal e grava `artifacts/night-attack.png`.
