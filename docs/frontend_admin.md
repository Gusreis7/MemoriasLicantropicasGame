# Painel do observador

Branch: `feat/painel_admin`. Entrada independente `frontend/admin.html`, com código em `frontend/admin/`. A coordenação serve o painel na porta 7078 e encaminha `/admin/api` ao FastAPI. Não depende de Phaser nem do bundle do jogo.

## Fluxo

- Ao abrir, consulta a sessão. Sem sessão válida, apresenta login de usuário e senha.
- Login envia JSON somente em POST para `/admin/api/v1/auth/login`. Cookies são administrados pelo navegador (`credentials: same-origin`); nenhum token é acessado pelo JavaScript, guardado em localStorage ou incluído na URL.
- A senha é apagada do formulário após cada tentativa. Falha 429 apresenta a limitação e não tenta novamente automaticamente.
- Logout usa `/auth/logout`; falha de rede é apresentada em vez de simular invalidação bem-sucedida.
- Qualquer resposta 401 posterior encerra a visualização e pede novo login.

O frontend é consumidor da autorização do backend; ocultar o painel não substitui a proteção das rotas no FastAPI.

## Telas

- Arquivo paginado de partidas, com seleção e estado atual.
- Visão geral: lobisomem sorteado, vivos, local do detetive e cartões dos sete personagens com retrato, papel e localização.
- Grafo SVG de encontros reais; ligações são acionáveis por mouse e teclado e abrem sua transcrição. Grafo vazio é apresentado como ausência de encontros, sem criar arestas fictícias.
- Mortes conhecidas com autoria somente quando registrada. Autoria `unknown` ou `killer_id` ausente é exibida como “Autoria não registrada”; nunca é inferida do sorteio.
- Conversas e transcrições paginadas (100 mensagens por página, sem limitar o total a 200). Filtro de participante atua na página atual, identificado no rótulo.
- Cronologia de eventos efetivados, paginada em 50 registros, com horário e origem.

Não há ações para alterar jogo, sorteio, personagens ou mensagens. A interface inclui estados vazios, carregamento, falhas recuperáveis e timeout HTTP de 10 segundos.

## Atualização e apresentação

A cada cinco segundos, enquanto a aba está visível, atualiza lista de partidas, estado, grafo e saúde. Não recria transcrições ou filtros durante leitura; a atualização manual inclui todos os painéis. O polling respeita foco na lista/grafo e respostas antigas de páginas/partidas são descartadas.

Tema de arquivo investigativo com papel, tinta verde e cobre. Layout responsivo; retratos são assets reais. Os valores externos são inseridos com `textContent` e criação de elementos; não são interpretados como HTML. Identificadores de retratos são codificados antes de compor caminhos.

## Contratos e validação

`api.ts` define os tipos e caminhos do contrato em `docs/contratos_visual.md`. Todos os requests admin usam prefixo `/admin/api/v1`, mesma origem e `cache: no-store`. Mensagens brutas do backend não são renderizadas em erros.

- TypeScript: `tsc --noEmit` aprovado.
- Nove testes unitários aprovados: transporte/login sem cache, sanitização 401/rede, 429 sem retry, logout 204, autoria desconhecida, autoria confirmada, evento inicial e data inválida.
- A validação visual no navegador e o build conjunto pertencem à integração da coordenação, após a outra entrada HTML estar disponível.

Nenhum dado de produção é simulado e nenhuma chamada AWS foi feita por esta frente.
