# Personagens e sorteio

O catálogo em `src/modules/characters/catalog.py` define fichas privadas e apresentações públicas. Os sete candidatos são Bentinho, Capitu, Escobar, Rubião, Virgília, Florença e Bacamarte. Floriano é o jogador; Brás Cubas é a vítima inicial e não participa do sorteio.

Cada criação usa `secrets.choice` no servidor para escolher exatamente um lobisomem. O estado privado é persistido antes da resposta; consultar a partida não sorteia novamente. O cliente não pode fornecer papel, seed ou elenco.

| Rota | Uso |
| --- | --- |
| `GET /api/v1/characters` | Catálogo público |
| `GET /api/v1/characters/{id}` | Apresentação pública de um personagem |
| `POST /api/v1/games` | Criar uma partida |
| `GET /api/v1/games/{id}` | Consultar a projeção pública da partida |

Biografias privadas, objetivos e papéis não são expostos pelo catálogo público. A composição usa `CatalogCharacterRepository`, `CharacterService` e `GameService`; as consequências dos turnos ficam nos serviços do jogo.

As relações e permissões de segredo são aplicadas pelo servidor antes de uma persona falar. Consulte [orquestração dos agentes](orquestracao_agentes.md) e [mesa determinística](mesa_deterministica.md). Alterações incompatíveis no formato de investigação não recebem migração automática.

Os testes em `tests/test_games.py` e `tests/test_api.py` cobrem sorteio e privacidade. O relatório histórico de mil criações pela API está em [reports/werewolf_draws_1000_20261105.json](reports/werewolf_draws_1000_20261105.json); ele documenta aquela execução, sem substituir a validação do código atual.
