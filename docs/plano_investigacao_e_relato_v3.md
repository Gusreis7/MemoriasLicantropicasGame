# Investigação v3: especificidade das provas e utilidade do relato

## Hipóteses a verificar

- A regra anterior aceita dois tipos (comum1+singular2+bonus1=4) com reconhecimento de propriedade, resolvendo cedo demais o caso.
- Repetições de relatos não estabelecem procedência ou participação no crime.
- Prompt longo e literário, estratégias de retenção, contexto não priorizado por pergunta, confiança65 quase inalcançável e reparo livre do mestre podem produzir respostas vagas/novas invenções.

## Direção de implementação

- Comuns com peso baixo e teto conjunto; peças pessoais decisivas, exame canônico para revelar marcas e participação material na cena. Identificação por dois relatos da mesma pessoa ou cópias do mesmo boato não cria corroboração.
- Catálogo cresce para sete apetrechos por pessoa: três exclusivos, um singular e três comuns. Preservar IDs e leitura dos saves; separar seleção por tipo de índices fixos de inventário. Descoberta pessoal a partir da segunda manhã, com caminhos viáveis para todos os culpados.
- Perguntas recebem informações autorizadas relacionadas ao assunto, em fala concreta com pessoa, local, motivo ou próximo passo. Segredos de vida pessoal podem abrir por progressão alcançável; a identidade de lobo continua protegida.
- Conquistas por fatos que Floriano realmente ouviu/descobriu, com fonte NPC e mensagem e sem desbloqueio por texto digitado pelo jogador. Não concedem pontuação de prova ou spoilers sobre tópicos ainda não revelados.

## Contratos e propriedade

| Frente | Branch / agente | Propriedade |
| --- | --- | --- |
| Provas e itens | feat/evidence_specificity / modelo principal | investigation/rules.py, catalog.py, interrogation.py, assembly.py, scoring.py e testes próprios |
| Relatos e descobertas | feat/actionable_dialogue_achievements / modelo principal | agents/, session_master/, knowledge/service.py, seeds.py, mechanics.py, characters/strategies.py, novo achievements/ e testes próprios |
| Interface e ícones | feat/investigation_discoveries_ui / modelo leve | frontend/game/main.ts,style.css,shared/api.ts,assets de itens e testes próprios |
| Integração e estudo | agente principal | contratos, investigation/service.py/router/schema.py, testes de integração, executor e relatório |

Evidence ganha examined=false, inspection_text=null e crime_link_verified=false (este último PRIVADO). `inspect_evidence(state,evidence_id,now) -> CaseTransition` fará exame idempotente. HTTP POST /games/{id}/evidence/{evidence_id}/inspect retorna CasePublic, sem dono/ligação privada.

Achievement tem id,title,description,unlocked_at e fonte opcional (mensagem/NPC). `InvestigationState.achievements` contém só desbloqueadas. PublicCase publica achievements e achievement_total=7. Helper award(state,id,now,source...) idempotente; personal_trace é concedida ao examinar peça pessoal. Demais IDs: marriage_triangle,seminary_bond,treatment_bentinho,florenca_father,capitu_separation,escobar_affection.

## Avaliação antes/depois

Congelar e2f2d62 em /tmp/ml-v3-baseline antes das alterações. Executar100 cenários na versão anterior e os mesmos100 na versão corrigida. Cobrir os sete candidatos e estilos de investigação, a viabilidade até o fim da partida e perguntas de pistas, álibis e relações. Identificar chamadas reais Qwen e políticas programadas separadamente.

Métricas: dia/caminho de vitória, recusas do delegado, influência de comuns versus raros, repetição de fontes, falsos positivos, informações úteis nas falas, evasão, metáforas, invenção, privacidade, conquistas por descoberta real, latência e tokens/custos. Predicados automáticos de utilidade são indicadores e exigem leitura qualitativa; não declaram uma resposta verdadeira somente por citar um nome.

Calibrar sem forçar taxa global de50%: uma política que investiga bem deve ter caminho consistente e levar mais de um dia; pegar comuns e acumular confirmações não deve bastar. Mais dificuldade de prova deve vir acompanhada de mais clareza de informação.

## Execução e decisões finais

As três frentes foram implementadas em worktrees e branches próprias. A frente de interface/ícones e a redação dos resultados usaram modelo leve; regras probatórias, autorização de segredos e integração ficaram com agentes do modelo principal. O trabalho foi integrado na exploração `AED/aed_investigation_v3` antes da entrega em `develop`.

- Foram acrescentados 14 exclusivos; cada NPC possui três exclusivos, um singular e três comuns. Itens repetidos continuam agrupados; examinar um exemplar atende à espécie sem multiplicar pontos.
- O delegado exige pelo menos 5 pontos, dois tipos, exclusivo examinado e corroboração externa. Comuns valem 0,25 com teto conjunto 0,5. Uma contradição pública pode substituir a segunda fonte externa.
- A API registra o último objeto apresentado por NPC, inclusive ao reapresentar um objeto antigo. Perguntas seguintes usam esse contexto sem criar outro depoimento.
- Relatos públicos deixam de depender de confiança alta. O contexto prioriza até três apoios pertinentes; o mestre escolhe um apoio autorizado para reparos, em vez de inventar uma nova fala factual. Confidências pessoais continuam condicionadas à relação.
- Sete conquistas são persistidas por partida e exibidas no caderno. Só contam descobertas ouvidas na fala final autorizada do NPC ou exame canônico, com desbloqueio idempotente; não dão bônus probatório.
- Perguntas de encaminhamento foram separadas de perguntas de álibi. O caderno só recebe pessoas/locais/observações efetivamente declarados, sem promover a atividade oculta inteira a evidência pública.

O estudo concluiu 100 cenários anteriores e 100 posteriores, com uma troca Qwen/mestre real por cenário e continuação programada da partida. A política completa venceu 40/40 nas duas versões, passando da primeira para a segunda manhã para a aceitação da prisão. Somente comuns passaram de 14/20 vitórias para 0/20; uma fonte, de 5/20 para 0/20. Isso valida os caminhos programados, não estabelece dificuldade para jogadores humanos. Parte do atraso decorre da disponibilidade do exclusivo na segunda manhã.

O indicador lexical de utilidade passou de 58/100 para 94/100 tentativas (94/99 respostas concluídas). Houve uma resposta bloqueada por revisão. A auditoria encontrou invenção de detalhes e atribuição de relação ao par errado; fidelidade narrativa continua parcial. Os dados originais foram preservados, inclusive a falha. Custo estimado registrado: US$ 0,12955590 antes + US$ 0,07549245 depois = **US$ 0,20504835**, segundo o snapshot configurado, não a fatura AWS.

Leia [o relatório completo](exploracao_investigacao_v3/relatorio.md), [as regras de provas](evidencias_especificidade_v3.md) e [os contratos de diálogo e descobertas](dialogo_descobertas_v3.md). A correção determinística de voz em primeira pessoa posterior ao congelamento do estudo tem validação de regressão separada; não foi retroativamente incluída nas métricas das 100 falas posteriores.

## Validação da entrega

- Backend completo: **676 testes passaram**, incluindo provas, mestre, segredos, compatibilidade e conquistas.
- Frontend: **44 testes passaram**, TypeScript e build Vite concluídos.
- Brave: **18 testes de fluxo passaram**, incluindo exame agrupado, notificações de conquista, continuação de conversa, assembleia e sequência da cadeia. Esses testes de interface usam respostas controladas; as chamadas Qwen reais estão no estudo separado.
- Redis real de testes em Docker: **44 testes passaram** de persistência, API e integração investigativa, com namespace exclusivo e limpeza por teste.
- Docker reconstruído com `compose.yaml` e `compose.aws-local.yaml`; HTTP 200 no jogo 7077, admin 7078 e health da API 7079. OpenAPI implantado inclui o exame e omite `crime_link_verified` da projeção pública. O admin sem login responde 401.

Os dados do Redis da aplicação foram preservados. Alterações simultâneas nos arquivos de arte/proveniência do Brás Cubas foram mantidas no workspace e não incluídas nos commits desta frente.
