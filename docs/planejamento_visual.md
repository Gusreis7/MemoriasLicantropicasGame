# Plano de execução — primeiro jogo visual

Status: **aprovado e implementado**. Resultado, configuração e evidências estão em [entrega_visual.md](entrega_visual.md). O texto abaixo preserva o plano aprovado.

A mecânica de conversa foi integrada em `develop` no commit `cfc7e33`. A branch local concluída foi removida; `main` e remotos não foram alterados. Este plano fica em `AED/aed_planejamento_visual`. Três subagentes fizeram análises somente de leitura sobre assets, mundo/mecânicas e admin; a delegação de implementação abaixo é a proposta para a próxima etapa.

## 1. Resultado esperado

Uma primeira experiência web 2D em que o jogador:

1. Cria ou retoma uma partida e assume Floriano na Praça Verde.
2. Anda para esquerda/direita em um cenário lateral, com animação e câmera acompanhando.
3. Vê NPCs presentes, aproxima-se e pressiona `E` para abordar.
4. Conversa por texto com a persona via Qwen/Mantle, usando as rotas e o harness existentes.
5. Fecha o diálogo, abre o mapa com `M` e escolhe outro dos cinco locais.
6. Volta ao mesmo NPC e retoma seu histórico; recarregar a página preserva partida e localização.

Em uma página separada, o operador consulta papéis secretos, localizações, conversas e eventos efetivamente registrados.

Este marco entrega exploração e diálogo. Turnos completos, assassinatos autônomos, investigação de pistas, encontros automáticos, combate, inventário e condições de vitória continuam para etapas posteriores. O painel não depende de inventar essas mecânicas para funcionar.

## 2. Direção visual e tecnologia propostas

Referência: pixel art acolhedora e expressiva, na linha visual de Stardew Valley, com identidade própria para o Rio ficcional de 1890. Fachadas, vegetação, calçamento, tecidos, madeira e iluminação em tons terrosos, verdes, âmbar e azul noturno. O movimento solicitado é lateral.

- **Phaser 4 + TypeScript + Vite:** cenas, sprites, câmera e colisões simples. Fixar a versão estável escolhida no lockfile ao implementar.
- **HTML/CSS sobre o canvas:** mapa, diálogos, retratos, menus e estados de espera, com texto legível e navegação por teclado.
- **Admin em TypeScript/HTML/CSS:** entrada e bundle separados, sem carregar o jogo Phaser; SVG interativo para o grafo pequeno.
- **FastAPI:** permanece um monólito modular; acrescenta `world`, `events` e `admin`, mantendo router/schema/service/repository.
- **Redis:** estado do mundo, índices, reservas e auditoria, além das partidas e conversas existentes.
- **Docker Compose:** builds e execução local; uv continua para Python. Ferramentas de frontend usam Node e npm com `package-lock.json` versionado.

Base lógica: `640×360`, com ampliação inteira e pixels nítidos, sem suavização. Cenas laterais com largura inicial de `1920` pixels lógicos. A interface textual pode usar resolução CSS independente do canvas. Letterboxing em telas com outra proporção evita distorção.

Referências técnicas: [releases oficiais Phaser](https://github.com/phaserjs/phaser/releases), [Arcade Physics](https://www.phaser.io/oss/docs/phaser/concepts/physics), [pixel art no Phaser 4](https://github.com/phaserjs/phaser/blob/master/docs/Phaser%204%20Pixel%20Art%20Guide/Phaser%204%20Pixel%20Art%20Guide.md) e [build do Vite](https://vite.dev/config/build-options).

O trabalho será local neste repositório, sem registro/publicação no hosting do Sites. A skill Sites orienta o fluxo local; imagegen orienta os assets raster.

## 3. Fonte visual dos personagens

Foram relidos os Markdown do projeto e todos os Markdown de `/home/gustavoreis/Documentos/QuemEOLobisomem`. A pasta de referência permanece somente leitura. As descrições abaixo são a fonte dos prompts; lacunas são identificadas como escolhas artísticas, não como fatos dos rascunhos.

| Personagem | Descrição física explícita | Proposta para complementar a arte |
| --- | --- | --- |
| Bentinho | 45 anos, branco, cabelo cacheado e bagunçado | Cabelo escuro, roupa escura ligeiramente desalinhada e postura tensa; cores do cabelo/olhos não foram definidas na fonte |
| Capitu | 40 anos, aparência jovial, ruiva, olhos dourados | Penteado preso parcialmente, vestuário de atendimento discreto; tom de pele e penteado são escolhas a definir na ficha visual |
| Escobar | 45 anos, moreno, cabelo cacheado, olhos verdes | Roupa sóbria e postura afável; cor exata do cabelo não foi definida |
| Rubião | 30 anos, moreno, cabelo liso, olhos escuros | Cabelo escuro e traje bem cuidado de herdeiro; roupa/cor do cabelo são propostas |
| Virgília | 33 anos, branca, loira, olhos castanhos | Coque loiro e vestido sóbrio com silhueta legível; penteado/vestuário são propostas |
| Florença | 28 anos, negra, olhos âmbar | Cabelo escuro preso e roupa prática de trabalho; cabelo/vestuário são propostas |
| Bacamarte | 35 anos, alto, moreno, óculos e jaleco | Silhueta mais alta dentro da célula comum, cabelo escuro e postura clínica; cabelo/olhos não foram definidos |
| Floriano | Ficha física vazia | Proposta inicial: homem adulto, pele morena, cabelos escuros, casaco curto castanho, camisa clara e caderneta; aparência inteiramente proposta para esta fase |

“Moreno” é preservado como está na fonte, sem converter automaticamente em identidade racial mais específica. A profissão/origem de Capitu não será transformada em sinal visual de culpa ou adereços caricatos.

Brás Cubas é a vítima inicial e não precisa de sprite vivo para esta exploração. Seu nome e morte conhecida aparecem na contextualização, sem inventar aparência ou autoria.

## 4. Contrato dos assets

Entregas previstas: **8 conjuntos de sprites** (jogador + 7 NPCs), **7 retratos de diálogo**, **5 cenários**, **1 mapa ilustrado** e atlas de elementos compartilhados quando necessário.

- Célula comum de sprite: `48×64`, com fundo transparente e pés ancorados no mesmo ponto. Silhuetas podem variar dentro dessa célula; Bacamarte permanece mais alto.
- Floriano: idle de 2 frames e caminhada de 4; esquerda/direita consistentes.
- NPCs: idle de 2 frames e pose/variação de conversa. Caminhada fica prevista no manifesto, sem exigir circulação autônoma nesta etapa.
- Retratos: `96×96` lógicos, expressão neutra reconhecível. Cores dos olhos precisam ficar perceptíveis nos retratos.
- Cenários: fundo lateral, chão/colisões e elementos de primeiro plano separados quando necessário. Nomes, placas e rótulos são desenhados pela interface, sem depender de texto gerado dentro da imagem.
- Mapa: bairro ficcional com os cinco destinos; não é reconstrução cartográfica do Rio.
- Manifesto por asset: `asset_id`, `path`, `frame_width`, `frame_height`, animações/frame indices, `origin`, escala e versão. IDs visuais devem corresponder aos IDs canônicos dos NPCs/locais.
- Aparência e arquivos são os mesmos nos papéis civil/lobisomem. Não haverá variante, nome de arquivo, aura ou posição inicial que entregue o sorteio.

Produção após aprovação: image_gen built-in, com referência visual comum, prompts/proveniência registrados e finais copiados para `frontend/public/assets/`. Primeiro produzir um piloto de Floriano, Capitu e Praça Verde para validar escala internamente; depois expandir o conjunto. Inspecionar transparência real, continuidade de identidade, grade, pivô e pés. Spritesheets geradas por IA podem exigir correção: não tratar qualquer imagem em grade como animação pronta. Protótipos temporários podem ajudar a desenvolver, mas assets reais são critério da entrega final.

Arte e dados terão pastas separadas por responsável: `assets/characters/`, `assets/portraits/`, `assets/locations/`, `assets/map/` e `assets/shared/`.

## 5. Cinco locais e distribuição inicial

Os três primeiros locais vêm das referências; **os dois últimos são propostas novas**.

| ID / local | Cenário e função | Presenças iniciais propostas |
| --- | --- | --- |
| `praca_verde` — Praça Verde | Hub inicial, árvores, bancos, calçamento e ponto de leitura do jornal | Floriano e Rubião |
| `cabana_capitu` — Cabana da Capitu | Área de atendimento, varanda e objetos de trabalho, com atmosfera íntima | Capitu e Virgília |
| `casa_verde` — Casa Verde | Fachada verde, portão e recepção/área externa acessível | Bacamarte |
| `cafe_largo` — **Café do Largo** | Café ficcional, mesas externas e balcão, espaço de convivência e fofocas | Bentinho e Escobar |
| `cais_lanternas` — **Cais das Lanternas** | Cais ficcional com barcos, cordas, armazém e lanternas; contraste urbano | Florença |

Essas posições são uma distribuição técnica inicial, independente do papel sorteado. Não acrescentam alianças, testemunhos, pistas ou álibis. NPCs permanecem em suas áreas neste marco; animações idle não significam ações autônomas.

O mapa permite escolher qualquer um dos outros quatro destinos. Viagem não consome dias ou ações enquanto o motor de turnos não estiver definido. Chegada usa um spawn seguro determinado pelo servidor, nunca coordenadas escolhidas pelo cliente.

## 6. Controles e fluxo da interface

- `A/D` ou setas: movimento horizontal.
- `E`: abordar o NPC destacado ao alcance.
- `M`: abrir/fechar o mapa de destinos.
- `Esc`: sair do mapa ou fechar a janela de diálogo quando não houver envio pendente.
- Durante digitação, as teclas não movem o personagem nem abrem o mapa.

A primeira entrega usa chão contínuo, limites e obstáculos simples, sem obstáculos que exijam salto. O foco é percorrer, viajar e investigar por conversa; salto/plataformas em alturas diferentes podem ser uma expansão.

O NPC próximo recebe contorno/ícone e indicação “E — Conversar”. O diálogo mostra nome, retrato, histórico, caixa de texto, estado “respondendo” e erro recuperável. Não haverá envio automático repetido após timeout. Enquanto a resposta está pendente, movimento/viagem ficam bloqueados no cliente e no servidor.

Ao voltar a uma persona, reutilizar a conversa jogador–NPC da partida, em vez de criar outra thread e perder o contexto. A memória entre diferentes pares ainda não se mistura. Ler o próprio histórico continua permitido à distância; iniciar/enviar conversa exige presença e alcance.

Criar nova partida tem ação explícita; atualizar o navegador ou trocar de cena nunca sorteia outro lobisomem. O navegador guarda apenas o ID da partida e preferências de UI; a posição canônica fica no Redis.

## 7. Mundo e contratos backend

Separar definições estáticas de mundo (`LocationDefinition`, layout/colisões/spawns) do estado por partida (`WorldState`, posição do jogador, presenças dos NPCs, sequência e revisão). O mundo terá `world_version` independente da versão de personalidade. Novas partidas inicializam mundo e índices junto de seu estado, sem alterar o sorteio. Este marco é validado com partidas novas; dados antigos são preservados, sem migração implícita ou re-sorteio.

O cliente desenha/anima a 60 FPS quando disponível. Movimento é comunicado em frequência baixa e limitada, por comandos de direção e sequência, sem chamar o LLM. O servidor calcula deslocamento usando tempo medido por ele, com duração máxima por comando, velocidade e limites conhecidos. O cliente prevê o movimento e reconcilia com o snapshot. Desconexão não permite continuar caminhando indefinidamente.

Proposta pública resumida:

```json
{
  "world_version": "1",
  "revision": 8,
  "player": {"location_id": "praca_verde", "x": 384, "facing": "right", "movement_seq": 12},
  "visible_npcs": [
    {"npc_id": "rubiao", "name": "Rubião", "x": 430, "sprite_id": "rubiao", "can_approach": true}
  ],
  "travel_targets": ["cabana_capitu", "casa_verde", "cafe_largo", "cais_lanternas"]
}
```

| Rota proposta | Responsabilidade |
| --- | --- |
| `GET /api/v1/world/locations` | Catálogo público dos cinco destinos/layouts |
| `GET /api/v1/games/{id}/world` | Posição/presenças visíveis e retomada |
| `POST /api/v1/games/{id}/movement` | Direção, sequência e local/revisão esperados; retorno canônico |
| `POST /api/v1/games/{id}/travel` | Destino e revisão esperada; spawn do servidor |
| `POST /api/v1/games/{id}/approaches` | Alvo; valida proximidade e obtém/cria thread jogador–NPC |

O contrato final de movimento será congelado antes da implementação paralela do cliente. Para o chão único proposto, a distância de abordagem inicial será de até 64 pixels lógicos no mesmo local e plano. Não prometer física/anti-cheat de plataforma vertical usando apenas um `x`.

Criar porta `InteractionPolicy.assert_can_talk(game_id, npc_id)` e injetá-la no service de conversas existente, para não permitir bypass por seus endpoints antigos. O módulo world implementa a porta sem depender do service de diálogo. Usar uma reserva por jogador/partida compartilhada entre envio e viagem para impedir corrida entre checagem de proximidade e mudança de local; comandos de movimento também respeitam a conversa pendente. Manter a reserva de conversa já existente.

Índice `(partida, player, npc) → conversation_id` garante retomada da thread. Schemas públicos nunca carregam papéis, objetivos privados, táticas ou transcrições de NPC–NPC.

## 8. Painel admin observador

Painel somente leitura, sem editar sorteio, matar NPCs, simular pistas ou disparar encontros.

Telas propostas:

1. Lista paginada de partidas e seleção da sessão.
2. Estado verdadeiro: lobisomem sorteado, papel de cada NPC, vivo/morto, localização e versões.
3. Conversas e transcrições paginadas, com filtros por participantes.
4. Grafo de interações reais: participantes, quantidade e última mensagem; clique na aresta abre a transcrição.
5. Timeline de eventos e mortes registradas, com autoria/proveniência quando conhecidas.
6. Estado técnico mínimo: dependências disponíveis, conversa ocupada e falhas sanitizadas.

Relações do roteiro e interações efetivamente ocorridas são camadas distintas. No início, as arestas reais podem ser apenas jogador–NPC. NPC–NPC só aparece se houver mensagens registradas; a interface não inventa encontros para preencher o grafo.

**Limite do campo “quem matou”:** hoje não existe motor de assassinato. Brás Cubas é a vítima inicial, com autoria **não registrada**. Ser o lobisomem sorteado não prova a autoria de cada morte; uma confissão em diálogo continua sendo mensagem. Preparar a tabela/contrato de mortes para consumir eventos futuros, sem atribuir assassinatos automaticamente.

Contratos admin separados, prefixo `/admin/api/v1`: `games`, `games/{id}/state`, `/events`, `/conversations`, `/conversations/{conversation_id}/messages` e `/interactions`. Não adicionar `include_secrets` à API do jogador.

Proteção: `ADMIN_TOKEN` no backend; o operador o informa no painel e ele fica somente na memória da aba, enviado no header de autorização. Todas as rotas admin validam a credencial no FastAPI. Não embutir segredo em variável `VITE_*`, bundle, URL ou payload público. O painel não recebe credenciais AWS, bearer Bedrock ou raciocínio interno do modelo. Separar portas ajuda a organização, mas não substitui a autorização.

## 9. Índices e eventos de observabilidade

O Redis atual não possui listagem global de partidas/conversas. Acrescentar índices pagináveis e log ordenado, com a mesma transação que efetiva a escrita correspondente:

- Índice de partidas e índice de conversas por partida.
- Eventos `game.created`, `world.initialized`, `player.travelled`, `conversation.created` e `conversation.exchange_committed`.
- ID de evento/causação e IDs de mensagens usados para evitar duplicação por reenvio.
- Grafo derivado de mensagens/eventos únicos, com contagem consistente.

Não registrar movimento a cada frame nem guardar prompts/credenciais nos eventos. Um log Redis Stream por partida é candidato; a projeção admin usa paginação e atualização leve enquanto a aba está visível, sem inferências.

Contrato de morte futura:

```json
{
  "type": "character.killed",
  "occurred_at": "UTC",
  "victim_id": "character_id",
  "killer_id": null,
  "attribution": "unknown",
  "source": "rules",
  "causation_id": "UUID"
}
```

Somente um futuro service de regras poderá efetivar esse evento com o estado da vítima. O evento inicial conhecido de Brás Cubas tem fonte narrativa e autoria desconhecida. Não expor esses campos secretos pelo snapshot do mundo.

As transações são planejadas para o Redis único atual. Índice global e registros por partida não implicam suporte Redis Cluster; não prometer atomicidade entre hash slots. Não fazer varredura geral de chaves a cada abertura do painel. Partidas antigas sem índice exigirão migração explícita ou aparecerão fora da listagem inicial, conforme documentado na implementação.

## 10. Portas e execução local após aprovação

| Porta/endereço | Serviço |
| --- | --- |
| `127.0.0.1:7077` | Jogo web e proxy somente da API pública |
| `127.0.0.1:7078` | Painel admin e proxy das rotas admin autenticadas |
| `127.0.0.1:7079` | FastAPI e documentação local |
| Sem porta pública por padrão | Redis na rede Docker |
| `127.0.0.1:7080`, opcional | Redis para depuração via perfil explícito |
| `127.0.0.1:7081`, somente desenvolvimento | Vite/HMR quando necessário |

Frontend terá build estático, servido por gateway local com entradas separadas para jogo/admin. Chamadas usam proxies de mesma origem; nenhuma chave AWS sai para o navegador. O deployment permanece Compose local; não publicar no Sites ou em cloud nesta etapa.

No desenvolvimento com perfil AWS, usar Redis/gateway em Docker e FastAPI no host, com `AWS_PROFILE=terraform`. No modo API em container, manter bearer por ambiente ou configurar acesso ao perfil explicitamente; não assumir que o login do host existe no container.

## 11. Delegação e branches após aprovação

Cada frente terá worktree/branch própria. A coordenação congela contratos e controla arquivos compartilhados (`compose`, dependências, composição, roteamento principal e configuração). Não haverá dois agentes editando o mesmo conjunto de arquivos.

| Responsável | Branch proposta | Entrega e limites de arquivos |
| --- | --- | --- |
| Coordenação | `feat/contratos_visual` | Contratos JSON/TypeScript/Python, manifestos e decisões em docs; integração dos arquivos compartilhados |
| Agente A — personagens | `feat/assets_personagens` | 8 sprites, 7 retratos, fichas visuais, prompts e manifesto em `assets/characters`, `assets/portraits` e docs de arte |
| Agente B — cenários/mapa | `feat/assets_locais_mapa` | 5 cenas, mapa, atlas comum, layouts/spawns/colisões e descrições em `assets/locations`, `assets/map`, `assets/shared` e docs de locais |
| Agente C — mundo/backend | `feat/mundo_localizacoes` | Módulo world, presença Redis, movimento, viagem, proximidade e retomada de thread; testes de regras/integração |
| Agente D — jogo/frontend | `feat/jogo_exploracao` | Phaser, câmera, animações, mapa e diálogo HTML; estados de carregamento/erro e testes do cliente |
| Agente E — observabilidade | `feat/observabilidade_admin` | Índices, eventos, autorização e projeções admin; testes de sigilo/atomicidade |
| Agente F — painel/frontend | `feat/painel_admin` | Lista/estado, timeline, grafo e transcrições; somente consumo das rotas admin |
| Coordenação/QA | `feat/integracao_visual` | Compose/portas, integração, testes completos, inspeção no navegador e documentação de execução |

Com quatro slots disponíveis, executar **no máximo três subagentes ao mesmo tempo**, além da coordenação:

1. Contratos e piloto: coordenação prepara interfaces, os agentes detalham arte/layouts, sem depender de backend pronto.
2. Primeira onda: A (personagens), B (cenários/mapa) e C (mundo/backend).
3. Segunda onda, após contratos/entregas necessários: D (jogo), E (admin backend) e F (admin frontend). O painel pode começar com fixtures claramente de teste, substituídas por dados reais antes da entrega.
4. Coordenação integra em `feat/integracao_visual`, verifica o resultado e prepara promoção para `develop` conforme aprovação. Branches locais concluídas são removidas depois de integradas; nenhuma promoção para `main`.

Produzir uma fatia jogável Praça → Capitu → diálogo antes de replicar os cinco cenários. A aprovação solicitada agora cobre o escopo; não implica novos pedidos de confirmação a cada escolha rotineira de implementação.

## 12. Critérios de aceite

- Jogo acessível em 7077 e admin em 7078, com API local em 7079.
- Cinco locais com assets reais, visual coerente, mapa clicável e viagem/retomada funcionando.
- Floriano anda lateralmente sem atravessar limites; teclado do diálogo não controla o mundo.
- Sete NPCs reconhecíveis, descrições físicas respeitadas e nenhum sinal visual do papel secreto.
- Abordagem próxima funciona e retomada mantém a mesma thread; chamadas diretas à API não burlam distância/local.
- Recarregar não perde a posição nem sorteia outra partida. Envio pendente bloqueia viagem/movimento e duplicação concorrente.
- Admin nega credencial ausente/inválida, mostra o sorteio correto e transcrições reais, incluindo NPC–NPC quando existirem.
- Admin diferencia autoria desconhecida, eventos de regras e alegações em falas. Não há dados inventados para preencher timeline/grafo.
- Schemas públicos/bundle do jogo não contêm papéis secretos, token admin, credenciais AWS ou históricos alheios.
- Regressão dos testes atuais mais testes novos de mundo/admin, em memória e Redis real; build Python/JS/Docker aprovado.
- Teste de navegador do fluxo criar → caminhar → abordar → conversar → viajar → voltar → retomar; suíte comum usa LLM simulado. Validação manual real com Qwen é separada, limitada ao fluxo aprovado.

Limites de QA visual serão informados se o ambiente não disponibilizar navegador. Não apresentar uma ilustração estática ou um mapa sem mecânica como jogo concluído.
