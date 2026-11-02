# Assembleia, itens e circulação visível

## Assembleia

`POST /api/v1/games/{id}/assembly` recebe o mesmo dossiê da acusação: `suspect_id`, `evidence_ids`, `testimony_ids`. Disponível durante o dia, uma vez por partida, inclusive quando não se alcança maioria. O cliente não escolhe votos nem resultado. A interface abre pelo botão Assembleia da cidade; seleciona-se um retrato e os registros antes de confirmar a convocação.

Votam Floriano e todos os NPCs vivos, livres e presentes na cidade, incluindo o acusado. Floriano vota pela proposta que apresentou. A maioria absoluta é `floor(total/2)+1`. O conjunto apresentado é anunciado aos eleitores: os civis avaliam as provas e a corroboração, com cautela diferente por persona; o acusado se defende. O lobisomem usa apenas seu próprio papel para se defender ou apoiar a expulsão de outro suspeito. Os votos desta versão são resolvidos por regras determinísticas e têm justificativas públicas; a redação do modelo não determina expulsões.

Maioria expulsa o acusado. Se for o lobisomem, vitória coletiva imediata (`ending.method=assembly`). Se for inocente, ele sai da cidade vivo e não participa de encontros, novas acusações ou vítimas noturnas. Afinidade não é reescrita; ressentimento aumenta5 e confiança diminui3 por par vivo e em relação a Floriano, dentro dos limites existentes. Sem maioria, ninguém sai; a convocação permanece consumida.

Caso, mundo, resultado, eventos e alterações sociais são gravados na mesma transação Redis, observando também o agregado social para impedir sobrescrita por um worker concorrente. Requisições concorrentes não permitem duas assembleias. A identidade do culpado permanece oculta quando não há expulsão. A expulsão de um inocente é pública, mas não revela o papel de terceiros.

## Circulação e conversas visíveis

NPCs caminham para encontros da agenda social existente (quatro oportunidades por dia). Viagens persistem origem, destino, rota e horários. A projeção interpola o movimento em cada rua e respeita as bordas de entrada/saída do catálogo. A caminhada no mesmo local usa65px/s; viagens reservam12 segundos por ligação. Um NPC em trânsito aparece caminhando, mas não pode ser abordado até chegar. Não há simulação de álibis passados a partir dessa animação.

O mapa mostra os moradores por local, com destino durante viagem e indicação de conversa. O cenário anima sprites e interpola posições entre consultas, mantendo o fundo estático. Falas efetivamente confirmadas aparecem por até12 segundos quando Floriano está no mesmo local a até180px do personagem; prompts e pensamentos privados não são expostos. Sem credenciais ou quando a fala do modelo é recusada, não se inventa uma conversa: o encontro pode terminar sem fala confirmada. `SOCIAL_ENABLED` precisa estar ativo para os encontros autônomos.

## Objetos

Os20 símbolos existentes foram redesenhados em SVG nativo numa grade32×32, ampliada com contornos em degraus, sombras simples e paleta limitada. Sem curvas, gradientes ou suavização. Os IDs e significados permanecem os do catálogo. Caderno, apresentação, delegado e assembleia usam os mesmos símbolos; a versão na URL evita reaproveitar o atlas antigo do cache.

## Validação

Testes cobrem maioria correta, expulsão inocente, ressentimento persistido, bloqueio noturno, concorrência, rejeição de votos fornecidos pelo cliente, convocação única e projeção da caminhada. Brave verifica o resultado público da assembleia e a atualização dos moradores no mapa, além dos fluxos existentes de provas, interrogatório e seleção por retrato. Captura: `artifacts/assembly-pixel-items.png`. Suíte normal usa inferência simulada e Redis isolado; não houve nova campanha de chamadas AWS nesta entrega.

Resultado: **523 testes Python** com Redis real, **39 testes frontend**, build TypeScript/Vite e **cinco fluxos Brave** aprovados. O build Docker também foi conferido no Brave com uma assembleia real sem provas: proposta recusada, convocação consumida e mapa com os sete moradores.
