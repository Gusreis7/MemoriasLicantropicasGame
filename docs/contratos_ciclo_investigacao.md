# Contratos — dias, crimes, apetrechos e acusação

## Execução e responsabilidades

Integração: `feat/ciclo_investigacao`; agentes em worktrees isoladas nas branches `feat/turnos_crimes`, `feat/pistas_delegado` e `feat/interface_investigacao`. Depois dos testes, merge em `develop` e remoção das branches integradas. Sem promover `main` ou publicar remotamente.

| Frente | Arquivos de propriedade |
| --- | --- |
| Ciclo e Redis | `modules/turns/**`, bootstrap `RedisGameRepository.create`, status em `contracts/model.py` e `modules/games/schema.py`, testes próprios |
| Pistas e delegado | `modules/investigation/**`, catálogo privado de itens, regras puras e projeção pública, testes próprios |
| Interface | `frontend/game/**`, `frontend/shared/api.ts`, testes de frontend; sem alterar assets |
| Coordenação | `contracts/investigation.py`, composição, rotas/main, integração de mundo/conversa/harness/admin, arte da capoeira, fixtures e verificação Docker/Brave |

## Regras da primeira versão

Dia de300 segundos UTC de servidor, noite de8 segundos não jogável. GET sincroniza fases vencidas sob reserva por jogador; não é um relógio fornecido pelo cliente. A recuperação após ausência processa as noites vencidas, no máximo até o fim da partida. Dois clientes não duplicam mortes, pistas ou manhãs. Partidas legadas começam o ciclo na migração explícita lazy, mantendo o sorteio e as conversas.

Na manhã, o mundo reposiciona o jogador na Praça Verde x160, diante da banca O Clarim do Rio. O jornal sempre publica uma edição: morte e localização pública ou ausência de morte. A noite escolhe somente civis vivos, excluindo o preso; interesses documentados orientam a preferência da vítima e o sorteio decide entre alternativas elegíveis. O lobisomem mantém o papel. Se todos os civis morrerem, derrota. Se o preso for lobisomem, sua transformação confirma a vitória e a expulsão. Inocente é solto pela manhã. Uma tentativa de acusação por dia e uma detenção por noite.

Cada NPC tem exatamente cinco itens: um exclusivo, um singular compartilhado por2–3 personagens e três de um conjunto de dez comuns. A propriedade é privada; o inventário do jogador contém apenas vestígios recolhidos. Evidência física é gerada pelas regras, nunca pela narrativa do LLM. O crime inicial de Brás Cubas passa a ter vestígios do assassino sorteado nas novas partidas; seu nome não entra no elenco vivo. Para legados, a inicialização do ciclo é registrada e não altera o sorteio.

Uma busca exige mesma localização e distância≤90px de crime.x. Cada busca recolhe um vestígio ainda não encontrado; repetir não duplica. Apresentar exige pista recolhida, NPC vivo, livre, no mesmo local e distância≤64px. O mesmo par pista/testemunha reaproveita seu depoimento, impedindo rerrolagem de resposta. A fala pública distingue reconhecimento, negação e desconhecimento; sua veracidade e o dono real são privados.

O delegado decide sem consultar papéis: ao menos dois tipos de objeto recolhidos, uma identificação registrada e pontuação mínima4 (exclusivo3, singular2, comum1, corroboração1). Apenas pistas ligadas ao acusado pelo conjunto dos depoimentos apresentados sustentam a acusação; testemunhos e itens duplicados não aumentam a pontuação. Boato em texto livre não conta como fato. A decisão informa critérios públicos, nunca revela se acertou antes da noite.

## Interfaces internas

Fonte dos modelos: `contracts/investigation.py`. `InvestigationState` é privado e contém fases, crimes, evidências, testemunhos, acusações e jornal; nunca retorná-lo diretamente.

`TurnService(redis, prefix, games, characters, world_repository, player_gate, clock=None)` expõe:

- `sync(game_id) -> InvestigationState`: reserva, processa vencimentos e retorna estado privado.
- `require_day_locked(game_id) -> InvestigationState`: chamador já detém a reserva; sincroniza e exige dia ativo.
- `act(game_id, transition) -> InvestigationState`: reserva, sincroniza/exige dia, carrega game/world e chama `transition(state, game, world) -> CaseTransition`. Persiste estado e eventos atomicamente; revisão é do servidor.
- `assert_dialogue_open(game_id)`: valida relógio/fase antes da persistência da resposta, sem adquirir reserva recursiva.

Cada commit noturno altera agregado, `GameState` (alive/status), `WorldState` (revisão/spawn) e eventos em uma transação Redis WATCH/MULTI. Regras não podem aceitar um papel diferente ou sobrescrever sorteio. Registro inválido gera erro sanitizado; sem escrita parcial se uma chave de eventos tiver tipo incorreto.

`InvestigationService(turns, characters)` expõe `get(game_id)`, `search(game_id, crime_id)`, `present(game_id, evidence_id, npc_id)` e `accuse(game_id, suspect_id, evidence_ids, testimony_ids)`; respostas sempre `CasePublic`. Valida acesso físico na transição usando world/game fornecidos pelo TurnService. Métodos de regras puras: `make_initial_investigation(game, now, day_seconds=300)`, `make_crime(game, day, victim_id, location_id, now)`, `choose_victim(game, detained_npc_id=None)`; implementação em `modules/investigation/rules.py`, importação desses helpers pelo ciclo. O relógio para depoimentos/acusações é fornecido pelo TurnService (`now()`), nunca pelo cliente.

## API acordada com o frontend

- `GET /api/v1/games/{id}/investigation` → `CasePublic`.
- `POST /api/v1/games/{id}/crime-scenes/{crime_id}/search` body `{}` → `CasePublic`.
- `POST /api/v1/games/{id}/evidence/{evidence_id}/present` body `{npc_id}` → `CasePublic`.
- `POST /api/v1/games/{id}/accusations` body `{suspect_id,evidence_ids:[UUID],testimony_ids:[UUID]}` → `CasePublic`.

`CasePublic`: `game_id,revision,day,phase,status,server_time,phase_ends_at,seconds_remaining,journal,crimes,inventory,testimonies,accusations,detained_npc_id,ending`.

`journal`: lista `{day,title:"O Clarim do Rio",headline,body,victim_id,victim_name,location_id,detention_outcome}`. `crimes`: lista `{id,day,victim_id,victim_name,location_id,x,remaining_clues}`. `inventory`: lista `{id,crime_id,item_id,name,kind,description}`. `testimonies`: lista `{id,day,evidence_id,witness_id,witness_name,recognition,claimed_owner_id,text}`. `accusations`: lista `{id,day,suspect_id,suspect_name,evidence_ids,testimony_ids,accepted,reason}`. `ending`: `null` durante o jogo; `{result:"won"|"lost",message,werewolf_id}` somente ao terminar (papel revelado no desfecho).

Frontend consulta aproximadamente a cada1 segundo, interrompe comandos à noite, sincroniza world após mudança de dia e abre jornal. Exibe crime próximo, caderno de provas/depoimentos, apresentação dentro do diálogo, delegado e desfecho. Nenhuma rota recebe relógio, vítima, resultado de reconhecimento, aceitação, papel ou coordenadas de chegada.

## Propostas posteriores

Proveniência de rumores, confronto de versões, álibis e exame detalhado são propostas de evolução, não dependências escondidas desta entrega. NPC–NPC autônomo e decisões de morte por LLM continuam fora da primeira versão. A roda de capoeira é ambiental e não recebe papéis de suspeito.
