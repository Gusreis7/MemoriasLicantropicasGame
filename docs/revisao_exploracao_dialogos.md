# Revisão de exploração e diálogo

Execução autorizada pelo autor em novembro de 2026. Integração em `feat/revisao_exploracao_dialogos`, com promoção para `develop` após os testes; `main` permanece sem alterações.

## Frentes e contratos

| Frente | Branch | Responsabilidade |
| --- | --- | --- |
| Coordenação | `feat/revisao_exploracao_dialogos` | Mundo compacto, conexões validadas, assets, integração e Docker |
| Parser | `fix/contrato_respostas` | Normalização antes da memória/API, contrato da fala e histórico legado |
| Guarda | `feat/guarda_dialogos` | Política determinística de entrada/saída, sem inferência ou ferramentas |
| Exploração | `feat/exploracao_cenarios` | Canvas fixo, escolha de saídas, figurantes, controles e testes Brave |

Os agentes trabalham em worktrees isoladas. O parser consome `DialogueGuard.inspect_input(text)` e `inspect_output(text, private_markers=())`, que retornam `GuardDecision(allowed, reply, reason)`. O motivo é interno; a recusa pública é uma fala diegética segura. Classificar uma tentativa não executa ações nem muda o estado da partida. O adaptador Mantle continua sem ferramentas e recusa tool calls.

O transporte LLM é separado do conteúdo do personagem. A saída aceita fala simples ou o envelope estrito `{remetente, fala}`, com remetente validado; a API e o Redis recebem somente a fala. Resposta inválida gera erro genérico; conteúdo bloqueado recebe recusa segura. Tentativas bloqueadas não entram no contexto futuro como instruções. Veja [contrato_respostas.md](contrato_respostas.md) e [guarda_dialogos.md](guarda_dialogos.md).

## Mundo compacto e passagens

Os cinco cenários têm 960 × 360, chão y300 e faixa x32–928. A câmera é fixa: apenas os personagens e a decoração móvel mudam de posição. O fundo é uma imagem estática por local. Sprites principais passam a 64 × 88; suas fichas e aparência permanecem independentes do papel secreto.

`LocationPublic.exits` contém `{side, target_location_id, arrival_side}`. A mesma lista orienta o menu e a validação do servidor. `TravelRequest` recebe `exit_side` opcional: omitido, preserva a viagem pelo mapa; informado, exige proximidade da borda (56px) e conexão válida. A chegada fica 96px para dentro da borda definida pelo servidor, voltada para o cenário. O jogador também pode escolher ir à outra ponta do mesmo local; isso exige uma saída válida pela posição e nunca ocorre automaticamente. A sequência de movimento e o sorteio permanecem preservados. Eventos registram origem, destino e bordas na transação CAS.

Praça liga Cabana/Café pela esquerda e Casa Verde/Cais pela direita. Cabana e Café se ligam pelas respectivas bordas esquerdas; Casa Verde e Cais, pelas direitas. Todas as ligações são recíprocas. O menu permite ficar, sem abrir repetidamente antes de o jogador recuar.

Partidas antigas podem conter x acima de928. A leitura do repository projeta essas posições para a faixa atual, sem gravar no GET e sem ressorteio. A próxima ação grava a projeção por CAS. O modelo de persistência mantém o limite legado apenas para conseguir ler esses registros.

Figurantes, árvores, cães, gatos e pássaros são decoração local. Não entram no elenco de sete suspeitos, não recebem papel, conversas ou capacidade de criar fatos da investigação.

## Verificação

Testes cobrem parser/guarda, privacidade, respostas adversariais, conservação do estado e eventos, conexão por borda, retomada, movimentação e interface em Brave. As chamadas de modelo dos testes usam stub; não é necessário consumir inferência real para esta revisão.

Resultados da entrega:

- **280 testes Python aprovados**, tanto com fakeredis quanto com Redis real isolado em Docker (`pytest -q --redis-url redis://127.0.0.1:16379/0`).
- **21 testes Vitest aprovados** e build TypeScript/Vite concluído, incluindo o build final em Docker.
- **3 fluxos Playwright aprovados no Brave instalado**: exploração/conversa/admin; comparação de pixels do fundo e passagens; envelope JSON, recusa de tentativa maliciosa e continuidade de perguntas normais.
- Build servido pelo Docker validado no Brave em7077/7078: assets, cenário960px, guarda local sem AWS, estado preservado, bloqueio de admin no gateway público, login, sete suspeitos, um lobisomem e logout.
- Cabeçalho e fechamento do diálogo permanecem visíveis com histórico longo; somente o histórico rola. O botão de ficar tem contraste no fundo claro. Capturas em `artifacts/game-world-static.png`, `artifacts/game-exit-choices.png`, `artifacts/game-dialogue-guard.png` e `artifacts/deployed-dialogue.png` (artefatos locais ignorados pelo Git).

Os serviços permanecem disponíveis em `http://localhost:7077` (jogo), `http://localhost:7078` (admin autenticado) e `http://localhost:7079/docs` (API). Os dados Redis e a configuração de credenciais existentes foram preservados. Nenhuma chamada real ao Qwen foi necessária nesta revisão.

## Arte entregue

As cinco imagens em `frontend/public/assets/locations/{id}.png` foram simplificadas usando **image_gen built-in** em modo de edição com referência. O novo atlas raster transparente está em `frontend/public/assets/ambient/scene-life.png`, acompanhado do recorte em `scene-life.json`. O manifesto `frontend/public/assets/characters/manifest.json` registra a exibição64×88. Fontes, dimensões, hashes e os prompts completos dos fundos e do atlas estão em [prompts.json](../frontend/public/assets/ambient/prompts.json). Não houve edição de pixels por script; código apenas copiou imagens finais e mediu o alfa para os metadados do atlas.

Os limites heurísticos da guarda estão documentados em [guarda_dialogos.md](guarda_dialogos.md): a política reduz ataques conhecidos, enquanto permissões e ausência de ferramentas executáveis continuam garantidas pelos serviços.
