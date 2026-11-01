# Primeira entrega visual

Plano aprovado e implementado com branches/worktrees isoladas. Integração final em `develop`; sem promoção para `main` ou push remoto. Skills usadas: Sites (fluxo local) e imagegen (geração raster built-in). A pasta de referência do autor não foi alterada.

## Funcionalidades

- Jogo pixel art lateral, cinco locais, mapa de viagem e retomada da posição no Redis.
- Floriano animado e sete NPCs, com retratos e aparência fiel à referência quando definida.
- Abordagem por proximidade, diálogo Qwen pelo harness existente e retomada da mesma thread ao reencontrar a persona.
- Gate por jogador impede viagem/movimento durante resposta; endpoints antigos também aplicam proximidade.
- Partida e mundo são inicializados com índices e eventos na mesma transação. Mensagens repetidas pelos mesmos IDs não duplicam eventos.
- Admin observador: estado secreto, locais, mortos/vivos, transcrições paginadas, grafo e timeline reais.
- Login por usuário/senha com hash scrypt em memória, cookie HTTPOnly/SameSite Strict, sessão Redis expirada, logout, limitação de tentativas e checagem de Origin. Sem senha configurada, o login falha fechado.

O jogo permanece um protótipo de exploração e conversa. Não há ainda motor de assassinatos, turnos completos, vitória/derrota ou encontros autônomos NPC–NPC. O admin mostra Brás Cubas como vítima inicial com autoria não registrada; não infere autoria pelo papel de lobisomem ou por alegações em diálogos.

## Executar

```sh
uv sync --locked
uv run python scripts/configure_local.py
docker compose -f compose.yaml -f compose.aws-local.yaml up -d --build
```

O segundo comando preserva valores existentes, preenche senha admin forte se ausente e mantém `.env` com permissões0600. Credenciais de acesso: campos `ADMIN_USERNAME` e `ADMIN_PASSWORD` desse arquivo local, nunca incluído em Git. É possível alterá-los e recriar a API. Para apenas gerar outra senha, usar `--reset-admin-password` explicitamente.

| Endereço | Uso |
| --- | --- |
| http://localhost:7077 | Jogo |
| http://localhost:7078 | Admin autenticado |
| http://localhost:7079/docs | API local |

Redis fica interno ao Compose. `compose.debug.yaml` publica somente emlocalhost7080 quando incluído explicitamente. O Redis dos testes usa16379, sem compartilhar o volume do jogo. `docker compose down` preserva os dados; não usar `down -v` para reinício comum.

O overlay `compose.aws-local.yaml` seleciona o perfil AWS (`terraform` por padrão). A pasta `${HOME}/.aws` é montada somente para leitura em `/aws-source`; o startup copia para um tmpfs privado em `/home/app/.aws` para permitir a renovação de `aws login`. Credenciais não entram na imagem, Git ou volume persistente e desaparecem com o container. Após renovar o login no host, recriar a API se necessário para recarregar a fonte.

Sem esse overlay, `docker compose up -d --build` usa a API key Bedrock fornecida por ambiente. A aplicação não recebe automaticamente a sessão CLI do host. O browser nunca recebe credenciais AWS.

Para desenvolvimento fora do container:

O frontend fora do Docker requer Node.js24 e npm; o build Docker já inclui essas ferramentas. Para a suíte de navegador, Brave deve estar instalado no host.

```sh
docker compose -f compose.yaml -f compose.debug.yaml up -d redis
REDIS_URL=redis://localhost:7080/0 AWS_PROFILE=terraform uv run uvicorn memorias_licantropicas.main:app --port 7079 --reload
cd frontend
npm ci
npm run dev
```

O Vite usa7081 e proxy da API7079. Abrir `/admin.html` no Vite exige incluir sua origem em `ADMIN_ALLOWED_ORIGINS` apenas durante desenvolvimento. O modo Docker usa as origens7078 configuradas por padrão.

## Contratos e conteúdo

Referências: [contratos visuais](contratos_visual.md), [mundo](mundo.md), [frontend do jogo](frontend_jogo.md), [autenticação/admin](admin.md) e [frontend admin](frontend_admin.md).

Assets finais em `frontend/public/assets/`: 8 spritesheets com48frames via atlas, 7retratos, 5cenários e mapa. Os PNGs têm resolução de origem maior que a grade lógica; atlas/metadados registram enquadramento e pivôs reais. A renderização adapta para o mundo lógico. Papéis civil/lobisomem usam exatamente a mesma arte.

Proveniência e prompts finais: [personagens](provenance_personagens.json), [direção de arte](art_direction.md), [cenários e mapa](locais_visuais.md) e `frontend/public/assets/locations/prompts.json`. Todos foram gerados pelo image_gen built-in e salvos no projeto.

## Validação realizada

- **124 testes Python aprovados em memória e124 com Redis real em Docker.**
- **16 testes TypeScript aprovados**, além de typecheck e build Vite.
- Teste de ponta a ponta no **Brave instalado**: criação, caminhada, abordagem, conversa simulada, mapa, viagem, retorno à mesma thread, recarga, login, papéis, transcrição e logout.
- Build e execução reais do Compose, com gateways7077/7078 e API7079; CSP validada com os recursos blob usados pelo Phaser.
- Uma resposta real do Qwen recebida/persistida pelo fluxo servido no Docker; login e estado admin também conferidos no Brave contra esse ambiente.
- `npm audit` após atualização das dependências: zero vulnerabilidades reportadas na instalação.

Os testes comuns continuam sem AWS: `tests/browser_server.py` fornece inferência determinística em servidor/namespace isolados; não é um modo falso da aplicação de produção. `frontend/e2e/deployed.mjs` testa o build servido e só chama o modelo real se `REAL_LLM_SMOKE=1` for explicitamente definido.

```sh
uv run pytest -q
docker compose -p ml-test-suits -f compose.test.yaml up -d --wait
uv run pytest -q --redis-url redis://127.0.0.1:16379/0
cd frontend
npm ci
npm test
npm run test:e2e
```

Playwright usa `/usr/bin/brave-browser` diretamente; `BRAVE_PATH` permite outro caminho. Não há instalação/download de Chromium pelos scripts. Screenshots de QA ficam no diretório ignorado `artifacts/`. Encerrar o Compose de teste após uso; manter o principal rodando para jogar.

## Limites atuais

API do jogador é local, sem contas de jogadores/propriedade multiusuário; apenas o admin tem autenticação. O mapa e distribuição são ficcionais e fixos. Caminhada é horizontal em chão contínuo; não há salto ou plataformas verticais. A memória está na thread do par jogador–NPC, sem recuperação automática entre pares distintos. Não há replay idempotente da inferência inteira: em erro/timeout, consultar histórico antes de reenviar.

Partidas antigas sem mundo/índice não são migradas silenciosamente. Criar nova partida usa o mundo e catálogo atuais sem alterar dados antigos. Recuperação após falha de disco, Redis Cluster, testes de carga e deploy público não fazem parte desta entrega.
