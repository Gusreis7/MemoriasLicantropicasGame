# Planejamento — Memórias Licantropicas

## Objetivo e situação atual

Construir um jogo web de investigação no Rio de Janeiro de 1890, inspirado na estética e nas relações humanas da obra de Machado de Assis. O jogador interpreta o detetive Floriano e investiga a morte de Brás Cubas, estopim de uma série de crimes. Um dos NPCs é sorteado como lobisomem a cada partida.

O projeto também é um laboratório de agent harness, teoria de jogos, tool calling e orquestração. O progresso será incremental: regras verificáveis primeiro, agentes e experimentos sobre essa base depois.

A base inclui catálogo público, sorteio privado, repositories Redis, harness Mantle, exploração visual, admin autenticado e o ciclo de investigação com dias, crimes, provas e prisão. Builds Docker e acesso real ao modelo foram validados nas etapas anteriores; a suíte continua sem chamadas AWS. A evolução atual está em [plano_investigacao.md](plano_investigacao.md) e [contratos_ciclo_investigacao.md](contratos_ciclo_investigacao.md). As etapas abaixo também registram propostas futuras e não significam que toda a orquestração NPC–NPC já foi implementada.

Evolução na branch `feat/conversa_jogador_persona`: diálogo pela API, estratégias narrativas dos sete NPCs, reserva Redis e autenticação por perfil AWS, conforme [conversa_jogador_persona.md](conversa_jogador_persona.md). Nessa evolução, o build da API e 81 testes em cada backend de armazenamento foram aprovados; inferência real da nova rota segue fora da suíte.

## Decisões confirmadas

- API REST em FastAPI, Python e dependências gerenciadas por uv.
- Monólito modular, organizado por domínio, com routers, schemas, services e repositories.
- Jogo no navegador e execução por Docker.
- AWS como base de integração, com Qwen 32B via Bedrock Mantle.
- Redis para registrar interações jogador–NPC e NPC–NPC.
- NPCs com biografia, personalidade, objetivos civis e objetivos como lobisomem.
- Uma instância lógica de agente para cada NPC em cada partida, com memória própria.
- Turnos diurnos com abordagens do jogador e interações autônomas entre NPCs.
- Sorteio do lobisomem por partida; nomes dos arquivos de referência não fixam papéis.
- Trabalho em `feat/`, correções maiores em `fix/`, explorações em `AED/`; aprovação para `develop` (staging) e posterior promoção aprovada para `main` (produção).

As escolhas de implementação a seguir são propostas para executar essas decisões. Não definem regras narrativas ainda em aberto.

## Referência narrativa

Fonte consultada: `/home/gustavoreis/Documentos/QuemEOLobisomem`, somente para leitura. Conteúdo adaptado para o jogo será mantido neste repositório e versionado, sem dependência desse caminho na execução.

| Personagem | Motivação civil / relação central | Objetivo no papel de lobisomem |
| --- | --- | --- |
| Bentinho | Espionar Capitu; ciúmes de Escobar; hostilidade ao investigador | Matar Escobar |
| Capitu | Atender clientes, cuidar da medicação de Bentinho e esconder o desejo de separação | Atacar Floriano se ele perguntar demais; ir atrás de Escobar, conforme rascunho |
| Escobar | Manter-se perto de Bentinho, por quem é secretamente apaixonado | Matar Capitu |
| Rubião | Aproximar-se de Florença, que não corresponde a seu interesse | Matar Virgília |
| Virgília Neves | Amizade com Florença, fofocas e consultas com Capitu | Matar Rubião |
| Florença | Defender os direitos das mulheres; pai internado na Casa Verde | Matar Bacamarte |
| Dr. Bacamarte | Investigar a mente e o interesse de Floriano em licantropia | Matar ao acaso, interpretando sua condição como loucura |

Brás Cubas é a vítima inicial; Floriano é o jogador. Casa Verde, cabana da Capitu e Praça Verde integram os locais descritos nas referências. O jornal comunica acontecimentos públicos. Os objetivos são particulares deste universo ficcional.

Pendências narrativas: completar Floriano, detalhar pistas e oportunidades de cada assassino, esclarecer o objetivo de Capitu e como o crime inicial se conecta a qualquer NPC sorteado. Bacamarte exige separar papel real de consciência do próprio papel.

## Primeiro ciclo jogável proposto

1. Criar uma partida, instanciar o elenco e sortear exatamente um lobisomem entre os NPCs elegíveis.
2. Gerar o estado inicial coerente com esse sorteio, a morte de Brás Cubas e as informações públicas/privadas.
3. Durante o dia, permitir ao detetive escolher um NPC vivo e conversar por uma quantidade limitada de mensagens, ainda a definir.
4. Executar uma rodada limitada de encontros entre NPCs. Eles trocam mensagens e atualizam crenças a partir do que puderam observar ou ouvir.
5. Encerrar o dia; resolver ações noturnas, possíveis crimes e pistas pelas regras do sistema.
6. Publicar os acontecimentos autorizados no jornal e iniciar o próximo dia.
7. Permitir uma acusação do jogador e resolver o desfecho conforme as condições de vitória/derrota definidas.

Para a primeira versão, propõe-se uma partida por jogador, sete suspeitos e ações em ordem explícita. Sem multiplayer humano, voz ou simulação contínua em segundo plano no primeiro ciclo. A tecnologia da interface permanece em aberto.

## Arquitetura proposta

```text
Navegador → API REST → routers → services → repositories → Redis
                                   │
                                   └→ harness de agentes → adaptador LLM → Bedrock Mantle
```

Uma aplicação e um deploy. Redis e Bedrock são dependências externas ao processo. Routers cuidam do HTTP; schemas definem contratos; services executam casos de uso e regras; repositories encapsulam persistência. Models representam estado do domínio, sem pressupor banco relacional ou ORM.

| Módulo | Responsabilidade |
| --- | --- |
| `characters` | Catálogo versionado, fichas, locais e relações iniciais |
| `games` | Partidas, papéis secretos, fases, elegibilidade de ações e desfechos |
| `conversations` | Conversas, participantes, mensagens e visibilidade |
| `agents` | Montagem de contexto, decisões, crenças e execução de ferramentas |
| `turns` | Ordem de execução, encontros, resolução noturna e recuperação de turnos |
| `journal` | Publicação de eventos que podem ser conhecidos pelo jogador |
| `infrastructure` | Conexões Redis, adaptador Bedrock, configuração e telemetria |

Estrutura de referência por módulo, criando arquivos apenas quando necessários:

```text
src/
  main.py
  modules/
    games/
      router.py
      schema.py
      service.py
      repository.py
      model.py
    characters/
    conversations/
    agents/
    turns/
    journal/
  infrastructure/
    redis.py
    llm/
      client.py
      bedrock_mantle.py
  content/
    characters/
    locations/
```

Cada módulo é dono de seu estado. Colaborações passam por interfaces de services, sem acesso direto ao repository de outro módulo. A montagem das dependências fica no ponto de composição da aplicação. Regras do jogo devem ser testáveis sem AWS e sem Redis.

## Estado, memória e rede de agentes

Separar três categorias de informação:

- **Verdade do jogo:** papel sorteado, ações efetivadas, mortes, locais e pistas existentes. Controlada pelo motor de regras.
- **Conhecimento e crenças individuais:** observações, relatos recebidos, suspeitas e segredos pessoais. Podem estar incompletos ou errados.
- **Discurso:** o que foi efetivamente dito em uma conversa. Um relato não vira fato automaticamente.

Entidades previstas: `Game`, `CharacterDefinition`, `CharacterState`, `Relationship`, `Conversation`, `Message`, `Observation`, `Belief`, `Action`, `Turn` e `JournalEntry`. Identificadores de partida e personagem acompanham todo estado mutável. Cada mensagem/evento registra participantes, dia/fase, ordem e origem; crenças referenciam suas evidências.

O grafo é lógico: personagens são nós; relações, encontros e mensagens formam arestas direcionadas. Todos podem potencialmente conversar, mas cada encontro depende das regras. Não é necessário introduzir banco de grafos para representar isso no MVP.

Proposta Redis:

| Chave ilustrativa | Conteúdo |
| --- | --- |
| `game:{id}:state` | Estado e versão da partida |
| `game:{id}:npc:{npc_id}` | Estado privado do personagem |
| `game:{id}:conversation:{conversation_id}:messages` | Sequência de mensagens da conversa |
| `game:{id}:npc:{npc_id}:knowledge` | Observações, crenças e resumos acessíveis ao NPC |
| `game:{id}:events` | Registro ordenado de eventos e ações efetivadas |
| `game:{id}:turn:{turn_id}` | Status, etapas concluídas e resultados do turno |

Redis já foi escolhido para interações. Propõe-se também usá-lo para o estado ativo no MVP, a validar na etapa de persistência. Definir persistência em disco/volume, recuperação, retenção e política de remoção antes de depender desse estado. Histórico original e resumo ficam separados; resumir não apaga evidências. Não introduzir embeddings ou busca vetorial antes de medir sua necessidade.

## Harness e orquestração

Uma instância de agente significa identidade, contexto e estado próprios, e não um processo ou modelo dedicado por NPC. O harness coordena cada invocação:

1. Receber ator, evento e ações permitidas na fase.
2. Montar contexto com ficha, consciência do papel, objetivos ativos, observações acessíveis e memória relevante.
3. Consultar o modelo com limites de tokens, tempo e quantidade de ferramentas.
4. Validar a saída e os argumentos das ferramentas com schemas.
5. Validar elegibilidade, alvos e regras no service responsável.
6. Persistir o resultado autorizado e atualizar apenas os participantes/observadores apropriados.
7. Registrar uso de tokens, duração, erros e versão de prompt/modelo.

O modelo propõe falas e ações. O código decide se uma ação é válida e aplica seus efeitos. Uma fala como “matei alguém” não efetiva uma morte. Uma mensagem do jogador não concede ferramentas nem altera papéis.

Ferramentas iniciais candidatas: consultar a própria memória, consultar o jornal público, propor encontro e registrar suspeita com evidências. Ação noturna é restrita por papel e fase e tem alvos validados. Nenhum agente recebe acesso direto ao Redis ou uma ferramenta genérica de leitura do estado global.

O lobisomem pode mentir; civis podem se enganar e esconder interesses. O conhecimento do próprio papel deve ser explícito, especialmente para Bacamarte. Nenhum prompt recebe automaticamente os segredos dos outros NPCs.

Começar com encontros sequenciais e número máximo de ações por NPC/turno. Uma rede de sete personagens já tem 21 pares possíveis: não executar todos a cada rodada. Definir seleção de pares, direito de recusa e limites de falas. Impedir cadeias ilimitadas de convites e ferramentas.

Manter versão de estado e uma execução ativa por partida; repetir uma requisição não pode duplicar turno, mensagem ou crime. Não manter transação de banco aberta enquanto aguarda o LLM. Persistir progresso de cada etapa para recuperar falhas sem repetir efeitos concluídos. Paralelismo só será experimentado depois, com regras explícitas sobre quando novas mensagens ficam visíveis.

## Integração AWS a validar

A documentação consultada lista Qwen3 32B com ID Mantle `qwen.qwen3-32b`, endpoint `https://bedrock-mantle.{region}.api.aws/v1`, Chat Completions e tool calling do lado da aplicação. Fonte: [ficha oficial Qwen3 32B no Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-qwen-qwen3-32b.html).

A primeira exploração deve confirmar se esse é o Qwen 32B pretendido, disponibilidade na conta/região, autenticação, endpoint, limites e formato real de chamadas de ferramenta. Não presumir que todo recurso de outro endpoint Bedrock esteja disponível no Mantle.

Manter região, modelo e endpoint configuráveis, com segredos fora do repositório. Usar um adaptador de inferência e um substituto determinístico para testes. A exploração inclui diálogo em português, saída estruturada, ferramenta inválida, timeout e throttling; documenta latência e consumo observados. Chamadas reais são validações específicas, não requisito da suíte comum de testes.

O destino de hospedagem da API e do Redis na AWS e o mecanismo de infraestrutura como código ficam para uma etapa posterior; a escolha de Bedrock não determina esses serviços.

## Contratos REST candidatos

Prefixo proposto: `/api/v1`. Contratos finais serão definidos com os casos de uso.

| Método e rota | Finalidade |
| --- | --- |
| `POST /games` | Criar partida sem expor o sorteio na resposta |
| `GET /games/{game_id}` | Consultar estado visível ao jogador |
| `GET /games/{game_id}/characters` | Consultar fichas públicas e disponibilidade |
| `POST /games/{game_id}/conversations` | Iniciar abordagem permitida |
| `POST /games/{game_id}/conversations/{conversation_id}/messages` | Enviar mensagem ao NPC |
| `GET /games/{game_id}/conversations/{conversation_id}/messages` | Recuperar histórico autorizado |
| `POST /games/{game_id}/turns` | Solicitar avanço/resolução do turno |
| `GET /games/{game_id}/turns/{turn_id}` | Consultar progresso e conclusão |
| `GET /games/{game_id}/journal` | Ler acontecimentos publicados |
| `POST /games/{game_id}/accusations` | Acusar e resolver conforme as regras |

Usar schemas de saída distintos do estado interno, paginação para históricos e erros consistentes. Operações demoradas podem retornar `202` e um recurso de acompanhamento; a execução deve sobreviver a reinícios antes de adotar esse contrato. Acesso à partida e identidade do jogador precisam ser definidos antes de exposição pública.

## Etapas e critérios de conclusão

Cada etapa deve produzir algo demonstrável e documentar o aprendizado. Não são estimativas de prazo. Ramos partem de `develop` quando estabelecida; este planejamento não cria branches, merges ou deploys.

| Etapa / branch sugerida | Entrega | Critério de conclusão |
| --- | --- | --- |
| 0 — `AED/aed_regras_e_pistas` | Regras mínimas, fichas normalizadas e cenários por assassino | Cada NPC elegível tem motivo, oportunidade e pistas coerentes; abordagem, acusação e desfechos definidos |
| 1 — `feat/base_modular` | Limites de módulos, configuração, injeção de dependências e contratos de erro | API inicial preservada; testes e Docker validados; módulos sem dependências circulares |
| 2 — `feat/motor_de_partidas` | Catálogo, sorteio, fases e regras com repositories em memória | Partida simulada do início ao desfecho sem LLM; sorteio único, transições e ações inválidas testados |
| 3 — `feat/memoria_redis` | Redis no Compose, repositories, históricos e recuperação | Reinício preserva estado esperado; partidas e memórias isoladas; ações repetidas sem efeitos duplicados |
| 4 — `AED/aed_qwen_mantle` | Prova técnica do adaptador e relatório de limites | Diálogo em português e ferramenta executada/validada; falhas e consumo documentados na conta/região escolhida |
| 5 — `feat/dialogo_npc` | Conversa jogador–NPC, contexto privado e memória | NPC mantém identidade e recorda a conversa; não recebe segredos alheios; falha de inferência não corrompe estado |
| 6 — `feat/turnos_multiagente` | Encontros NPC–NPC, crenças, noite e jornal | Dia completo com execução limitada e recuperável; rumores não se tornam verdade; NPC morto não age |
| 7 — `feat/interface_investigacao` | Interface web para diálogos, jornal, turnos e acusação | Jogador termina uma partida pelo navegador, com feedback de espera e recuperação de erros |
| 8 — `AED/aed_avaliacao_agentes` | Cenários comparáveis, métricas e experimentos | Comparação registrada entre políticas de memória/encontros com orçamento e versões identificados |
| 9 — `feat/staging_aws` | Hospedagem, persistência, acesso, configuração e operação documentados | Partida completa em staging, recuperação exercitada e promoção para produção sujeita à aprovação |

Dependências: 0 → 1 → 2 → 3; 4 pode ocorrer independentemente de 1–3. A etapa 5 exige 3 e 4; 6 exige 5; 7 usa os contratos de 5–6; 8 exige o ciclo completo; 9 exige a validação do MVP.

## Validação e aprendizado

- **Regras:** sorteio entre elegíveis, isolamento de segredos, fases, mortes, pistas e condições de término.
- **Persistência:** histórico ordenado, recuperação, concorrência por partida e idempotência de operações.
- **Harness:** ferramenta desconhecida, argumentos inválidos, tentativas de acesso indevido, limite de iterações e falhas do provedor.
- **Integração:** dois NPCs conversam e só eles recebem o conteúdo privado; jornal divulga apenas o que foi publicado; uma crença incorreta pode circular sem alterar fatos.
- **Ponta a ponta:** criação → abordagem → encontros → noite → jornal → acusação → desfecho.
- **Avaliação narrativa:** fidelidade à personalidade, coerência com o que o NPC sabe, qualidade das pistas e investigabilidade, usando rubricas e revisão de amostras.
- **Teoria de jogos:** comparar políticas de compartilhar/ocultar informações e seleção de parceiros; observar sobrevivência, propagação de rumores e sucesso do detetive. Não impor votação ou vitória coletiva do party game sem definir isso como mecânica.

Registrar seed do motor, versões de conteúdo/prompts/modelo, ações, mensagens, falhas, tokens e duração. Seed reproduz o sorteio e regras aleatórias; não garante reprodução exata de respostas do LLM. Para replay fiel, usar as respostas registradas. Dados internos de depuração não ficam disponíveis ao jogador durante a investigação.

## Decisões de produto ainda abertas

1. Uma abordagem equivale a uma mensagem ou a uma conversa? Quantas abordagens e mensagens cabem por dia?
2. O jogador decide quando encerrar o dia? Quantos encontros autônomos ocorrem em cada rodada?
3. Como uma acusação é feita, quais evidências exige e o que acontece em caso de erro?
4. Quais são as derrotas: morte do detetive, prazo, limite de vítimas ou combinação?
5. Como funcionam deslocamentos, locais, testemunhas, álibis e descoberta de pistas?
6. Quais crimes são obrigatórios, como o objetivo particular influencia o alvo e o que ocorre quando esse alvo morre? A chance de 30% por noite é hipótese do rascunho, não regra aprovada.
7. O quanto cada personagem sabe sobre a própria condição e sobre o sobrenatural?
8. Qual o orçamento de inferência por turno/partida e a latência aceitável para jogar?
9. Qual tecnologia de interface e qual identidade/sessão do jogador serão usadas no MVP?

Próxima entrega recomendada: fechar a etapa 0 em um documento curto de regras e cenários, antes de implementar o motor de partidas. Isso define os contratos que a API e os agentes precisarão respeitar.
