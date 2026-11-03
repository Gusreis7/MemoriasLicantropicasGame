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
