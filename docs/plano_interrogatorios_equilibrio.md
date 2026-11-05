# Interrogatórios, cooperação civil e avaliação

## Escopo aprovado

Todos os civis desejam identificar o lobisomem, com cooperação limitada pelo conhecimento, confiança e interesses pessoais. Floriano vence por prisão confirmada na noite ou confissão validada. O lobisomem vence se permanecer desconhecido até o desfecho de derrota existente (nenhum civil vivo); uma recusa isolada ou confissão inventada pelo jogador não comprova papel.

## Contratos e delegação

Trabalho na branch `feat/interrogatorios_simulacoes`, preservando as alterações locais anteriores de convivência. Integração final em develop após validação. Frentes com propriedade de arquivos distintas:

1. Interrogatórios: `contracts/investigation.py`, `modules/investigation/**`, `modules/turns/**`, testes novos próprios. Implementar depoimento sobre dia/noite, local, companhia e atividade; distinguir alegação de registro factual; conhecimento desigual e cooperação por NPC; confrontar com vestígios/depoimentos, dificuldade por personagem e confissão autorizada pelo motor. Informar contratos HTTP cedo à integração.
2. Uso e admin: novos módulos de uso/medição, infraestrutura de telemetria, `composition.py`, settings/env, `modules/admin/**`, frontend admin e testes próprios. Medir todas as inferências por game_id e finalidade, inclusive saídas rejeitadas, registrar tokens desconhecidos como desconhecidos; custo estimado USD com taxas e fonte explícitas e configuráveis. Nunca contabilizar créditos promocionais como tarifa zero. Contexto de uso deve ser isolado por tarefa assíncrona.
3. Simulações: `scripts/run_session_simulations.py`, testes e docs próprios. Dez partidas isoladas e repetíveis, cobrir os sete papéis, ambas as vitórias e falhas. Política do detetive decide com projeções públicas, sem olhar o culpado. Avaliar memórias/fontes, cooperação e fidelidade semântica com chamadas reais quando disponíveis; reportar falha de autenticação ou cobertura incompleta honestamente. Seed não reproduz LLM; salvar respostas e métricas.
4. Integração: interface de interrogatório/confissão e caderno, harness e política social, documentação final, Docker/Brave e revisão dos contratos. Acrescentar objetivo civil coletivo sem apagar objetivos canônicos individuais.

## Regras de integridade

Álibis históricos precisam apontar para um registro do motor ou para uma alegação atribuída; movimento presente não comprova posição passada. Sem fonte acessível, NPC admite desconhecimento. Depoimentos repetidos preservam versão original, novas versões precisam referenciá-la. A dificuldade de confissão não é pública como detector de papéis. Somente o motor registra confissão e vitória, em transação com estado da partida. Noite, morte, prisão e fim continuam limitando ações. Nenhuma fala pode alterar pistas, papéis ou custos por instrução do usuário.

## Avaliação

Rodar dez simulações registrando resultado, papel (apenas auditoria), dias, pistas, interrogatórios, acusações, confissões, falas, latência, consumo e violações. Amostra exploratória; não estima equilíbrio populacional. Comparar investigação com evidências, acusação insuficiente, prisão errada e passividade. Verificar preservação da fonte, ausência de conhecimento indevido e uso das memórias com modelo real. Testes determinísticos verificam integridade; a avaliação narrativa registra limites sem confundir conformidade estrutural com fidelidade semântica.
