# Contratos de implementação visual (aprovados)

O plano `planejamento_visual.md` foi aprovado. Trabalho local, sem publicação remota/cloud. Cada frente usa worktree própria. Coordenação controla compose, dependências/lockfiles, composition.py, main.py, settings.py, RedisGameRepository/RedisMemoryRepository, ConversationService e fixtures compartilhadas. Agentes não editam esses arquivos sem combinar.

## Arte e frontend

`frontend/public/assets/characters/{id}.png`: spritesheet horizontal com seis células iguais (2 idle + 4 walk) quando viável; metadados reais em `characters/manifest.json` com `id,path,frameWidth,frameHeight,frames,idleFrames,walkFrames,displayWidth,displayHeight,origin`. Se necessário sprite sem grade é identificado explicitamente, sem recortes presumidos. IDs: player, bentinho, capitu, escobar, rubiao, virgilia, florenca, bacamarte. Base lógica48x64, pés em (0.5,1). Imagens produzidas via image_gen built-in, transparência verdadeira. Retratos `portraits/{npc_id}.png`. Camadas finais de imagem não podem ser placeholders.

`frontend/public/assets/locations/{location_id}.png`: imagem lateral, adaptável visualmente a um mundo1920x360 com piso em y=300. Câmera640x360. Os assets gerados podem ter resolução maior e metadados devem refletir dimensões reais; o frontend faz enquadramento/escala coerente. Mapa em `assets/map/city.png`, rótulos HTML/SVG fora da imagem.

5IDs: praca_verde (player spawn160, Rubião em440), cabana_capitu (Capitu440, Virgília900), casa_verde (Bacamarte460), cafe_largo (Bentinho460, Escobar900), cais_lanternas (Florença480). Viagem spawn160. Todos os locais width1920 height360 ground_y300. Campo de interação64px. Posições e sprites não mudam com sorteio.

## Mundo — agente responsável

Arquivos próprios: `modules/world/{model,schema,catalog,repository,service,router,gate}.py`, `tests/test_world.py`, `docs/mundo.md`. Construtores combinados: `RedisWorldRepository(client,prefix)`, `RedisPlayerGate(client,prefix,timeout_seconds=40)` com `hold(game_id)` async context manager; `WorldService(games,characters,repository,gate)`. `WorldService` expõe `get(game_id)`, `move(game_id,body)`, `travel(game_id,body)`, `assert_can_talk(game_id,npc_id)`. Gate deve ter a MESMA chave quando usado pela coordenação no envio de diálogo.

Exportar `make_initial_world(game_id)` em world/model.py ou catalog.py (avisar local exato), modelo Pydantic com model_dump_json. Chave `prefix:game:{UUID}:world`. Coordenação chama ao inserir partida (transação com estado/índice). Mundo ausente retorna409 (partida antiga), não resorteia. Gate key `prefix:game:{UUID}:player:busy`, reserva com proprietário/TTL e timeout, não Lua. Mundo muda por CAS/revision e reserva por jogador. Travel gera evento via Redis mesmo transaction de update, conforme formato abaixo.

Rotas públicas: `GET /api/v1/world/locations`; `GET /api/v1/games/{game_id}/world`; `POST /api/v1/games/{game_id}/movement`; `POST /api/v1/games/{game_id}/travel`.

Body movement: `{"direction":"left|right|idle","seq":1,"location_id":"praca_verde","revision":0}`. Comandos estritamente crescentes. Delta calculado pelo relógio servidor desde último comando, limitado a400ms; velocidade210px/s; cliente prevê/reconcilia, envia a cada150ms e imediatamente na parada. Player x limitado[32,1888]. Travel body `{"target_location_id":"cabana_capitu","revision":8}`.

Snapshot: `{"game_id":"UUID","world_version":"1","revision":8,"location":{"id":"praca_verde","name":"Praça Verde","width":1920,"height":360,"ground_y":300,"background":"/assets/locations/praca_verde.png"},"player":{"location_id":"praca_verde","x":384,"facing":"right","movement_seq":12},"visible_npcs":[{"npc_id":"rubiao","name":"Rubião","x":440,"sprite_id":"rubiao","can_approach":true}],"travel_targets":["cabana_capitu","casa_verde","cafe_largo","cais_lanternas"]}`. GET locations retorna lista de location objects acima (sem placements globais). Movimentos/viagens retornam snapshot. LLM nunca usado para movimento.

## Integração conversa — coordenação

`POST /api/v1/games/{game_id}/approaches` body npc_id, resposta mesmo ConversationPublic (id,game_id,npc_id,created_at). Create/send também validam policy de proximidade. Game/player gate antes do conversation gate. History continua legível à distância. Índice de thread `prefix:game:{UUID}:player_thread:{npc_id}`. Um par retorna sempre mesma conversa, sem perdê-la entre locais. O harness interno permanece sem regra de distância para futura orquestração NPCNPC; HTTP aplica a política.

## Admin — coordenação/backend

Login por usuário/senha configurados no backend (`ADMIN_USERNAME`,`ADMIN_PASSWORD`), senha comparada por hash scrypt e sessão aleatória Redis com expiração. Cookie HTTPOnly, SameSite Strict, rota `/admin/api`, Secure configurável para HTTPS. Logout invalida sessão. Limite de tentativas e validação de Origin no login/logout. Sem segredo hardcoded/bundle/URL. Padrão sem senha configurada falha fechado.

Frontend separado em `frontend/admin/`, entrada `admin.html`. Rotas `/admin/api/v1/auth/login` POST {username,password}, `/auth/session` GET usuário atual, `/auth/logout` POST. Todas as demais rotas exigem sessão. Consultas read-only: `/games?offset=0&limit=20`→{items:[{id,created_at,status}],total}; `/games/{id}/state`→{game_id,created_at,content_version,status,werewolf_id,characters:[{character_id,name,role,alive,location_id,x}],player,known_deaths:[{victim_id,victim_name,killer_id,killer_name,attribution,source}],world_version}; `/games/{id}/events?offset=0&limit=50`→{items,total}; `/games/{id}/conversations`→{items,total}; `/games/{id}/conversations/{cid}/messages?offset=0&limit=100`→{items:[{id,sender_id,content,created_at}],total}; `/games/{id}/interactions`→{nodes:[{id,name}],edges:[{source,target,message_count,last_at,conversation_id}]}; `/health`→estado sanitizado de Redis.

Eventos em lista JSON `prefix:game:{UUID}:events`, objeto {id,type,occurred_at,source,data}. Game index ZSET `prefix:games` score timestamp. Conversation index ZSET `prefix:game:{UUID}:conversations`, score timestamp. Eventos mínimos game.created,world.initialized,story.initial_death(victim bras_cubas killer null attribution unknown),player.travelled,conversation.created,conversation.exchange_committed. Idempotência por IDs, mesma transação que escrita de estado. Não inventar assassinatos ou tráfegoNPCNPC. Sem uso de SCAN na listagem normal.

## Execução e delegação

Primeira onda: assets personagens, assets cenários/mapa, backend mundo. Coordenação faz backend admin/config/contratos e prepara frontend. Segunda onda: frontend jogo e frontend admin em arquivos separados. Máximo três agentes simultâneos além do root. Builds com npm lock versionado; teste de navegador após ler skill Sites preview local. Portas7077 jogo,7078admin,7079API; Redis interno/debug7080; Vite7081 em dev. Proxies com API de mesma origem; gamegateway bloqueia /admin; admin autenticado no backend mesmo via7079. Suíte nunca chama AWS; modo de demonstração opcional explicitamente identificado não se confunde com Qwen real.
