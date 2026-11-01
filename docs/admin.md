# Backend admin e autenticação

Implementação da frente `feat/observabilidade_admin`. O módulo `admin` é um observador: não altera papéis, personagens, mortes ou mensagens. Índices/eventos são escritos atomicamente pelos repositories do jogo na integração da coordenação.

## Composição

- `AdminAuth(client, prefix, settings)` usa `settings.admin_username`, `admin_password` (`SecretStr` ou `None`), `admin_session_seconds`, `admin_cookie_secure` e `admin_allowed_origins` (origens separadas por vírgula).
- `AdminService(client, prefix, games, characters, worldrepository)` lê as portas existentes e os índices Redis.
- O router único `/admin/api/v1` espera `app.state.services.admin_auth` e `app.state.services.admin`. A composição principal registra o router e os handlers de `NotFoundError`/`StorageUnavailableError`.

## Login e sessão

O operador informa usuário/senha em `POST /admin/api/v1/auth/login`. A senha é comparada por scrypt (`n=16384`, `r=8`, `p=1`, salt aleatório por instância) e comparação constante. A derivação usada no login roda fora do event loop. A senha configurada não é armazenada pelo objeto de autenticação após derivação, nem retornada ou logada.

Sem senha configurada o login falha fechado com 503. Usuário ou senha incorretos recebem 401 com a mesma mensagem. Dez falhas por IP em cinco minutos bloqueiam tentativas seguintes com 429/`Retry-After`; o backend usa o IP da conexão e não confia em `X-Forwarded-For` arbitrário.

Sessão: token aleatório de 32 bytes, cookie `ml_admin_session`, `HttpOnly`, `SameSite=Strict`, `Path=/admin/api`, duração configurada e flag `Secure` configurável para HTTPS. O token original só existe no cookie; a chave Redis contém SHA-256 do token e o valor guarda usuário/data, nunca a senha ou o token em claro. Não há JWT ou segredo entregue ao JavaScript.

- `GET /auth/session` verifica a sessão e retorna somente o username.
- `POST /auth/logout` exige sessão, remove a entrada Redis e apaga o cookie.
- Login/logout validam `Origin` quando informado; origens fora da lista são rejeitadas com 403. Clientes CLI sem Origin continuam permitidos.
- Respostas admin recebem `Cache-Control: no-store`; autenticação funciona também ao acessar a API diretamente, sem depender de esconder a interface.
- Sessões têm prazo fixo e não renovam automaticamente a cada consulta. Expiração, logout e Redis indisponível falham fechados.

Todas as consultas de observação exigem a mesma sessão; não há opção `include_secrets` na API pública.

## Consultas

| Rota depois de `/admin/api/v1` | Resultado |
| --- | --- |
| `/games` | `{items,total}` com partidas indexadas, paginadas por offset/limit |
| `/games/{id}/state` | Sorteio real, papéis, vivos/mortos, posições, player, versão e mortes conhecidas |
| `/games/{id}/events` | Página cronológica dos eventos persistidos |
| `/games/{id}/conversations` | Conversas indexadas da partida |
| `/games/{id}/conversations/{cid}/messages` | Transcrição administrativa paginada, incluindo NPC–NPC |
| `/games/{id}/interactions` | Nós e arestas de conversas com mensagens reais; conversa vazia não vira aresta |
| `/health` | Estado sanitizado da conexão Redis |

Limites: offset não negativo e páginas de até 200 registros; a paginação de transcrições permite percorrer além das 200 mensagens. Conteúdos são projetados em schemas próprios. Não são devolvidos objetivos completos, prompts, credenciais AWS ou dump de Redis.

Listagens usam ZSET de partidas `prefix:games`, ZSET `prefix:game:{id}:conversations` e lista de eventos `prefix:game:{id}:events`. Não há SCAN na consulta normal. O grafo usa IDs únicos de mensagens e separa presença/roteiro de interação efetivamente ocorrida.

Brás Cubas aparece como vítima inicial com autoria desconhecida. Ser o lobisomem sorteado não atribui a autoria dessa morte. Uma frase confessando um crime permanece mensagem. Somente futuros eventos `character.killed` com fonte `rules` acrescentam fatos de autoria na projeção; este módulo não produz tais eventos.

## Validação

`tests/test_admin.py`: **21 testes aprovados isoladamente em memória**, sem AWS, cobrindo todas as rotas protegidas, cookie, sessão, expiração, logout, origem, rate limit, ausência de configuração, cookie Secure, estado verdadeiro, mortes desconhecidas, grafo vazio/real, transcrição acima de 200, paginação, dados corrompidos e não promoção de alegações a fatos. A integração completa e Redis real ficam a cargo da coordenação.

Limites desta fase: um usuário administrativo configurado; sem cadastro, recuperação de senha ou permissões por papel. O serviço é local nesta entrega. TLS e `ADMIN_COOKIE_SECURE=true` são necessários quando exposto em HTTPS fora do desenvolvimento local.
