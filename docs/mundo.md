# Mundo de exploração lateral

Branch de implementação: `feat/mundo_localizacoes`. Segue os contratos de `contratos_visual.md`; nenhuma inferência ocorre no módulo world.

## Integração

- `modules/world/catalog.py` exporta `make_initial_world(game_id) -> WorldState` para a transação de criação da partida. Ela não escolhe nem altera papéis.
- `RedisWorldRepository(client, prefix="ml:v1")` expõe `create`, `get` e `save(world, expected_revision, event=None)`. O bootstrap principal deve inserir o JSON inicial na mesma transação do estado da partida/índices; `create` existe para fixtures ou inicialização explícita.
- Chave do mundo: `prefix:game:{UUID}:world`; estado com `game_id`, `world_version`, `revision`, `player` e `npcs`. `player` inclui direção anterior e `last_updated_at` UTC internos. Os NPCs têm apenas ID, local e x, sem papel/objetivo.
- `RedisPlayerGate(client, prefix="ml:v1", timeout_seconds=40)` expõe `hold(game_id)` e usa a chave `prefix:game:{UUID}:player:busy`. A composição deve injetar a mesma reserva no diálogo para proteger viagem/movimento durante resposta.
- `WorldService(games, characters, repository, gate)` expõe `get`, `move`, `travel` e `assert_can_talk`. Um parâmetro opcional `clock` permite testes determinísticos; em produção usa UTC do servidor.
- `router` expõe catálogo em `/api/v1/world/locations` e estado/movimento/viagem em `/api/v1/games/{game_id}/world`, `/movement`, `/travel`. A dependência lê `app.state.services.world`.

Partida ausente produz `NotFoundError`. Catálogo incompatível ou mundo ainda não inicializado produz `ConflictError`, sem migração implícita, sorteio ou criação pelo GET.

## Catálogo e posições

Todos os locais têm largura1920, altura360, chão em y300, chegada x160 e faixa válida x32–1888. Os assets públicos são `/assets/locations/{id}.png`.

| Local | NPCs iniciais / posição x |
| --- | --- |
| Praça Verde | Rubião440 |
| Cabana da Capitu | Capitu440, Virgília900 |
| Casa Verde | Bacamarte460 |
| Café do Largo | Bentinho460, Escobar900 |
| Cais das Lanternas | Florença480 |

O snapshot contém somente NPCs vivos do elenco que estão no local atual, suas posições e a possibilidade de abordagem. Não retorna papéis, objetivos ou presenças globais ocultas. O catálogo público de locais não inclui a distribuição dos NPCs.

## Movimento e viagem

O movimento recebe direção, sequência, local e revisão. O servidor integra a **direção anterior** pelo tempo decorrido desde o último comando, limitado a400ms, à velocidade210px/s; depois registra a nova intenção. O primeiro comando inicia movimento, sem teleportar. Coordenadas não são aceitas como entrada. Após parada, comandos idle não movem o jogador. O cliente deve prever a caminhada e enviar comandos aproximadamente a cada150ms, incluindo a parada.

Sequências precisam crescer; local/revisão devem coincidir. Esses controles rejeitam comandos atrasados, repetidos ou enviados antes da viagem. Alterações usam revisão CAS e reserva por jogador. O cliente deve buscar estado atual após409 antes de retomar o fluxo.

A viagem aceita qualquer outro local conhecido, define spawn160, direção idle e facing right, e preserva a sequência de movimento. Não consome turno nem chama modelo. O evento `player.travelled` é acrescentado à lista `prefix:game:{UUID}:events` na mesma transação do mundo, com ID, data, origem e destino. Conflito não gera evento duplicado; tipo de chave inválido é detectado antes do MULTI para evitar atualização parcial.

## Abordagem e reserva

`assert_can_talk` exige NPC vivo, mesma localização e distância horizontal de até64 pixels, inclusiva. Ela não adquire reserva por conta própria: o service que chama o harness deve manter a reserva do jogador durante a checagem e toda inferência. Isso impede que o caminho HTTP de conversa contorne a distância ou viaje em paralelo.

Uma reserva concorrente recebe409 em vez de esperar. O token de proprietário é comparado em WATCH/MULTI antes de liberar, sem Lua. O timeout global termina antes do TTL, e falha durante liberação não esconde o resultado original; o TTL recupera reservas abandonadas.

## Limites

A física desta entrega é uma faixa horizontal contínua; não implementa salto, plataformas verticais, contorno de móveis, multiplayer ou antitrapaça completo. Renderização, câmera e animação pertencem ao cliente. NPCs não se deslocam autonomamente. Eventos de morte e turnos pertencem a outros módulos futuros.

Os testes do módulo cobrem integração por relógio controlado, limites, sequência/revisão, viagem e evento atômicos, privacidade do snapshot, alcance, NPC morto, gate compartilhado, corrupção e validação HTTP. Não usam AWS nem assets gerados.
