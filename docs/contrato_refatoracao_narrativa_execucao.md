# Contrato de execução da refatoração narrativa

Assembleia curta: abertura até 800 caracteres, uma resposta breve por morador, uma réplica de Floriano até 500 caracteres e votação final. Prazo máximo de 60 segundos, retomável, com compensação do relógio apenas pelo período limitado da sessão. Uma assembleia por partida. Cada eleitor escolhe o acusado, Floriano ou abstenção; só uma maioria absoluta expulsa. Floriano expulso encerra como derrota.

## Frentes e propriedade

- `feat/dialogue_session_master`: agents/, conversations/, novo session_master/, composition.py, investigation/service.py e turns/service.py para integração narrativa; testes de diálogo/mestre. Os trechos da assembleia em service/turns serão integrados pelo responsável principal após merge.
- `feat/social_mathematics`: contracts/social.py, modules/knowledge/, modules/social/, characters/strategies.py e catalog.py; testes sociais. Sem alterar a versão do catálogo por compatibilidade. Exportar `vote_scores(voter_id, suspect_id, relationships, proof_strength, argument_strength)` em `modules/knowledge/mechanics.py`, retornando scores para o suspeito e `player`. Valores de força entre 0 e 1. Função pura, sem acesso aos papéis secretos.
- `feat/natural_investigation_ui`: frontend/game/main.ts, frontend/game/style.css, frontend/shared/api.ts e testes UI próprios. Remover formulário de álibi/confronto; apresentar objetos como ação no chat, permitir continuação natural. Assembleia em janela própria, abertura e réplica curtas, alvo e anexos, transcrição e resultado com expulsão de Floriano.
- Integração principal: contracts/investigation.py, investigation/schema.py/router.py/assembly.py, integração final de assembleia em service/turns, simulações, relatório e build Docker/Brave.

## HTTP de assembleia

`POST /api/v1/games/{id}/assembly/open`: `suspect_id`, `evidence_ids`, `testimony_ids`, `speech` (máximo 800). Retorna `CasePublic` com `assembly_session`: `id`, `suspect_id`, `phase` (`debate`/`resolved`), `messages` (speaker_id, text), `deadline`, `opening_speech`, `reply` e anexos. Sessão aberta não revela votos. `POST .../assembly/resolve`: `reply` até 500 caracteres. Retorna `CasePublic` com resultado final em `assembly`; pode ser resolvido automaticamente no prazo. `assembly.outcome`: `werewolf`, `innocent`, `no_majority`, `player_expelled`. Votos incluem `voter_id`, `target_id` ou null, `expel`, `reason`. Manter endpoint legado `/assembly` compatível para clientes anteriores.

## Integração do mestre

Diálogo deve persistir a pista apresentada e sua resposta no histórico da conversa; contexto tem as atividades próprias mesmo sem formulário. Confidência pessoal e admissão no jogo não são vazamento técnico. O mestre distingue fala própria, citação, negação, hipótese, admissão parcial e rendição; produz propostas tipadas com IDs/trechos. O motor verifica papel e resolve confissão canônica sem botão de confronto. Persistência idempotente e resultado de término coerente com GameState e jornal. Novos dados privados não entram na projeção pública.

## Validação/exploração

Até 100 simulações reproduzíveis com regras reais importadas: parte para calibragem e parte independente, distribuindo lobos e estilos de jogador. Medir falsos positivos de confissão, vitória/derrota por política, voto em Floriano, evidências de influência das relações e independência das fontes. Distinguir simulação de regras, respostas programadas e chamadas reais de LLM. Não atribuir tokens medidos a chamadas simuladas; cenário de custos identifica tarifa configurada, estimativa de tokens e incerteza.
