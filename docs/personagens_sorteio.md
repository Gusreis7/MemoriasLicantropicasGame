# Personagens e sorteio — base v1

Registro da base v1. O catálogo atual é versão 3, com estratégias narrativas, segredos pessoais protegidos e rejeição de partidas antigas, conforme [conversa_jogador_persona.md](conversa_jogador_persona.md).

Branch: `feat/personagens_sorteio`.

## Plano executado

1. Adaptar as sete fichas dos rascunhos para um catálogo Python versionado, sem alterar a pasta de referência.
2. Separar biografias e objetivos privados das introduções públicas.
3. Criar repository do catálogo, services e schemas públicos de personagens e partidas.
4. Expor catálogo público e criação/consulta de partidas por routers; a composição injeta a persistência.

Não foram executados testes nem inferências, conforme instrução do usuário.

## Conteúdo e visibilidade

Fonte de conteúdo única: `modules/characters/catalog.py`, com `CONTENT_VERSION = "1"`, `CHARACTERS` e introduções `PUBLIC_BIOS`. O catálogo usa objetos internos `CharacterProfile` imutáveis. Personalidades foram sintetizadas a partir das relações e objetivos dos rascunhos; não são novas mecânicas.

IDs elegíveis: `bentinho`, `capitu`, `escobar`, `rubiao`, `virgilia`, `florenca`, `bacamarte`. Floriano (`player`) e Brás Cubas não participam do sorteio. O nome do arquivo original de Escobar não fixa seu papel.

A API pública de personagens retorna somente `id`, `name` e uma biografia de apresentação. Não retorna biografia privada, personalidade interna, objetivos civis, objetivos como lobisomem ou consciência do papel. A paixão secreta de Escobar e o desejo de separação de Capitu permanecem no conteúdo privado. Bacamarte possui `role_awareness="denial"`; interpretar essa condição é responsabilidade do harness.

O objetivo de Capitu preserva a ambiguidade do rascunho e a marca como pendência; esta entrega não define ações de ataque.

## Contratos REST

| Método / rota | Entrada | Resposta |
| --- | --- | --- |
| `GET /api/v1/characters` | Nenhuma | Lista de `CharacterPublic` |
| `GET /api/v1/characters/{character_id}` | ID estável | `CharacterPublic` ou erro de personagem inexistente |
| `POST /api/v1/games` | Corpo ausente, `null` ou `{}` | `201`, `GamePublic` |
| `GET /api/v1/games/{game_id}` | UUID da partida | `GamePublic` ou erro de partida inexistente |

Campos extras no corpo de criação são rejeitados pelo schema: o cliente não informa papéis, seed ou elenco. UUIDs inválidos são rejeitados pela validação FastAPI. Não existe endpoint de sorteio separado, nem de re-sorteio ou exposição do assassino.

`GamePublic` contém `id`, `created_at` UTC, `content_version`, `status="active"` e elenco com apresentação pública e `alive`. Cada criação gera novo UUID e usa `secrets.choice` no servidor para selecionar um dos sete perfis. O estado privado, com exatamente um lobisomem, é persistido pelo `GameRepository.create` insert-only antes da resposta. Ler a partida não sorteia de novo.

## Composição e dependências

- `CatalogCharacterRepository()` implementa `CharacterRepository.list/get` sem I/O.
- `CharacterService(repository)` oferece `list()` e `get(character_id)`, retornando schemas públicos.
- `GameService(characters, games)` recebe os dois repositories e oferece `create()` e `get(game_id)` com projeções públicas.
- Routers exportam `get_character_service` e `get_game_service`; a composição pode sobrescrever essas dependências. O catálogo possui default local; partidas exigem configuração explícita do service.
- `modules/games/repository.py` reexporta a porta compartilhada; sua implementação Redis é de responsabilidade da infraestrutura.
- Services lançam `NotFoundError`/`ConflictError`; a composição central faz o mapeamento HTTP. Nenhum service depende de FastAPI.

Não há autenticação/propriedade de partidas, turnos, mortes ou atualização de papéis nesta base. A API destina-se ao desenvolvimento local. Alterar catálogo no futuro exige uma estratégia de compatibilidade para partidas com versões anteriores.
