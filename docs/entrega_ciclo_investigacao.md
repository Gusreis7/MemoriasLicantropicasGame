# Entrega — ciclo de investigação

Implementação guiada pelo [plano apresentado durante o trabalho paralelo](plano_investigacao.md) e pelos [contratos entre agentes](contratos_ciclo_investigacao.md). As três frentes de ciclo, pistas e interface trabalharam em branches próprias; uma quarta revisão protegeu os novos campos do harness. A coordenação integrou os módulos, as políticas de ação, o admin e os assets.

## Regras disponíveis

- Dia de300 segundos e noite de8 segundos, controlados pelo UTC do servidor. Noite e desfecho bloqueiam caminhada, viagem, abordagem, busca, apresentação e acusação, tanto no cliente quanto na API.
- Ao amanhecer, Floriano retorna à Praça Verde x160, diante do sprite da banca O Clarim do Rio. O jornal publica a vítima/local ou ausência de morte. Os prazos e resultados persistem; recarregar não reinicia o relógio. Ausência longa processa noites vencidas até a derrota ou vitória.
- Cada um dos sete NPCs tem cinco apetrechos: um exclusivo, um singular e três comuns. São sete exclusivos, três tipos singulares e dez comuns no catálogo. A propriedade não é pública.
- A cena inicial de Brás Cubas e os crimes noturnos têm vestígios materiais coerentes com o assassino sorteado. Nas primeiras noites aparece um comum e um singular; a partir do crime do terceiro dia, um comum e o exclusivo. O jogador precisa estar próximo para recolher.
- Mostrar um vestígio a um NPC vivo e livre registra reconhecimento, negação ou desconhecimento. O mesmo par objeto/testemunha mantém o resultado. Os depoimentos aparecem no caderno e entram no contexto individual do NPC. O reconhecimento desta versão é resolvido pelas regras, sem uma inferência adicional; o LLM continua interpretando o diálogo livre com esses registros autorizados.
- O delegado avalia somente os fatos apresentados, sem ler papéis ou a veracidade privada. Exige dois tipos de objeto ligados ao acusado por depoimentos e pontuação mínima de corroboração. Há uma tentativa por dia. Aceitar significa custódia, sem confirmar culpa.
- A transformação do preso na noite confirma a vitória e a expulsão. O lobisomem sai das posições do mundo e aparece como expulso no admin; expulsão não é morte. Inocente é protegido naquela noite e solto pela manhã. Se morrerem todos os civis, há derrota. O jogador não é uma vítima elegível nesta versão.
- A roda de capoeira tem quatro poses animadas no Cais, atrás dos personagens. A preferência por redução de movimento mantém pose fixa. O fundo permanece estático.

## Integridade e limites

Investigação, estado vivo/morto, status, posição do jogador e eventos noturnos são gravados na mesma transação Redis. A reserva por jogador impede duas resoluções concorrentes. Consultas de uma fase ainda válida usam snapshot atômico sem disputar a reserva de uma inferência; fases vencidas exigem reserva. Não há worker adicional: a sincronização por consulta/ação materializa a passagem do tempo pelos prazos persistidos.

Uma resposta do modelo que chega depois do fim do dia é recusada antes de anexar a troca ao histórico. O modelo não determina vítima, cria objeto, concede prisão ou decide vitória. O contexto contém os próprios apetrechos, observações limitadas sobre dois conhecidos, jornal público e os próprios depoimentos; a guarda verifica pedidos de expor suas chaves técnicas e ecos das instruções.

O admin autenticado mostra o ciclo, custódia e o agregado privado em um painel de inspeção. Ao consultar uma partida, sincroniza os acontecimentos de tempo já vencidos; não oferece comandos de modificar papéis ou resolver noites antecipadamente. A rota de avanço de relógio do E2E existe somente em `tests/browser_server.py`, sem registro na aplicação ou imagem de produção.

Partidas anteriores sem agregado de investigação recebem inicialização do ciclo no momento da primeira sincronização, preservando o sorteio, conversas e os eventos existentes. Os novos vestígios iniciais são gerados para esse ciclo; não se reescreve o registro histórico original de Brás Cubas.

Encontros NPC–NPC autônomos, álibis, rumores rastreáveis, circulação de objetos e reputação do delegado são propostas no plano, sem implementação nesta etapa. O reconhecimento atual de apetrechos é uma base determinística; personalidade e objetivos continuam no diálogo livre.

## Verificação

- **373 testes Python aprovados** com fakeredis e novamente com Redis real isolado em Docker. Incluem os sete caminhos completos pela API até a vitória noturna, bloqueio de todas as ações à noite, preservação das pistas, vítimas/jornal reais, prisão errada, ausência de morte, derrota, catch-up, concorrência, corrupção e resposta de LLM que cruza o deadline.
- **27 testes Vitest aprovados**, incluindo relógio monotônico, bloqueio, busca e polling sem sobreposição. Build TypeScript/Vite aprovado na imagem Docker final.
- **Seis fluxos Brave**: regressões de exploração/diálogo/admin e proteção; dois fluxos da interface com contrato simulado; e ciclo integrado com Redis e backend reais. Este último verifica coleta, mudança de poses da capoeira, bloqueio noturno, morte, jornal e retorno à banca sem esperar cinco minutos reais. O avanço de relógio fica restrito ao executável de teste.
- Build servido pelo Docker verificado no Brave, com jornal, investigação, guarda local, login/admin e logout. Nenhuma inferência AWS foi necessária.

Artefatos locais ignorados pelo Git: `artifacts/cycle-evidence.png`, `artifacts/cycle-capoeira.png`, `artifacts/cycle-newspaper.png`, `artifacts/deployed-dialogue.png` e `artifacts/deployed-admin.png`.

## Arte e execução

Assets finais gerados por **image_gen built-in**: `frontend/public/assets/ambient/clarim.png`, `capoeira.png` e `assets/press/crime-scene-snapshot.png`, acompanhados de atlas/proveniência JSON. A banca mantém a identidade verde e cobre; o Clarim agora tem uma página completa em preto e branco, com textura de papel, masthead, manchete, relato, localização e uma ilustração monocromática da madrugada. A imagem é uma cena de arquivo reutilizada, enquanto manchete, texto e local vêm da edição real. Os vinte apetrechos usam símbolos vetoriais com IDs iguais aos do catálogo em `assets/items/item-icons.svg`; o mesmo desenho é exibido ao recolher, apresentar e citar um vestígio. A roda fica à direita diante do poste, avançada para o passeio em primeiro plano; os músicos e capoeiristas pisam no calçamento. Os capoeiristas usam lenços no pescoço, sem cordas na cintura. A árvore que encobria o poste do cais foi removida do asset de fundo e da decoração.

Prompts completos: [clarim-prompts.json](../frontend/public/assets/ambient/clarim-prompts.json), [capoeira-prompts.json](../frontend/public/assets/ambient/capoeira-prompts.json) e [snapshot-prompts.json](../frontend/public/assets/press/snapshot-prompts.json). O catálogo visual dos itens está em [manifest.json](../frontend/public/assets/items/manifest.json).

Serviços locais: jogo em `http://localhost:7077`, admin em `http://localhost:7078`, API em `http://localhost:7079/docs`. Docker usa os dados Redis e as credenciais já configuradas. O Redis de testes é separado e não precisa permanecer ativo depois da validação.
