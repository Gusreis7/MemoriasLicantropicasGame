# Entrega: conversa, relações, mestre e assembleia curta

## Implementação integrada

- Pistas apresentadas passam à cronologia real da conversa com IDs estáveis. Perguntas posteriores recebem o depoimento e o histórico. O painel de álibi/confronto foi removido; declarações naturais podem criar registros no caderno.
- Personas cooperam conforme personalidade e contexto, com fofoca e confidência condicionais. O contexto inclui atividades pessoais, não exige interrogatório formal prévio e traz resistência narrativa distinta por personagem.
- Relações direcionais têm afinidade, confiança, ressentimento, suspeita e lealdade; efeitos limitados e causados por eventos. Assuntos autorais semeiam o núcleo Capitu/Bentinho/Escobar/Bacamarte, inclusive medicação, ciúme e seminário. Cópias de boatos conservam a mesma origem.
- Mestre privado interpreta a troca, valida autoria/trechos, propõe efeitos e pode reparar a fala na mesma inferência. Confissão real ligada ao caso com entrega encerra exatamente uma vez, atualiza GameState, investigação e jornal. Negação, fala citada, inocente e prompt de repetição não concedem vitória.
- Assembleia em modal próprio: abertura800 caracteres, uma fala por NPC, réplica500 caracteres e votação. Prazo60 segundos; relógio de investigação compensado somente pelo período limitado do debate; ações e encontros sociais interrompidos/bloqueados enquanto ele ocorre. Reabrir/retomar não reinicia prazo nem concede nova sessão.
- Voto considera provas, argumento, credibilidade e vínculos. Moradores podem escolher o acusado, Floriano ou abstenção. Maioria contra Floriano encerra em derrota, com Clarim específico.
- Campos novos têm defaults para ler saves existentes; catálogo permanece v3. Não há alteração retroativa de resultados. APIs legadas de interrogação/confronto/assembleia continuam disponíveis para clientes antigos, mas a interface usa o fluxo natural e a sessão curta.
- Tokens e custo das novas tarefas `session_master` e `assembly_debate` usam a medição existente por partida. Reparo ocorre na chamada do mestre; não inicia terceiro LLM por mensagem. Persona tem saída limitada a240 tokens; mestre a640. Credenciais continuam no servidor.

## Frentes e branches

Contratos: `docs/contrato_refatoracao_narrativa_execucao.md`.

1. `feat/dialogue_session_master`: harness, guarda, memória imediata, mestre e encerramento.
2. `feat/social_mathematics`: atributos, fórmulas, sementes autorais e circulação de fofocas.
3. `feat/natural_investigation_ui`: chat, pista, assembleia e término por expulsão de Floriano.
4. `feat/short_assembly`: sessões, prazo, voto e regras de turnos.
5. `AED/aed_narrative_balance`: exploração, custos e correções encontradas na validação.

## Validação executada

- 595 testes de backend,43 testes unitários de frontend e16 cenários de navegador Brave passaram.
- TypeScript e build Vite concluíram; Docker reconstruiu API, jogo e painel com checks de saúde.
- Testes backend incluem fakeredis/ASGI e namespace isolado; testes Brave usam fixtures/mocks. Os dados de partidas em andamento do usuário não foram usados na exploração.
- 100 cenários contabilizados:21 tentativas com falha de inicialização do runner (preservadas),72 partidas completas com políticas programadas e7 encontros reais de Qwen, cada um continuado por três turnos. São21 trocas reais/42 chamadas, não100 partidas com LLM.
- Os artefatos desse experimento foram retirados do checkout; permanecem no histórico Git anterior à limpeza.

## Limitações e resultados não aprovados

As amostras reais ficaram mais concisas, mas a revisão manual ainda encontrou detalhes não sustentados mesmo após reparo. O mestre pode falhar semanticamente e sua correção pode inventar outro detalhe. A informação narrada por um NPC não cria automaticamente prova material, autoria verdadeira ou fato do mundo. Não se declara grounding plenamente resolvido.

As políticas informadas tiveram desempenho alto porque examinam sistematicamente os registros públicos; hostilidade foi exercitada com intervenções programadas fortes. A exploração valida caminhos e limites das regras, sem estabelecer dificuldade de jogadores humanos, equilíbrio competitivo ou taxa real de confissão espontânea. Esses pontos permanecem para sessões humanas e novas amostras, conforme o relatório.

O custo medido estimado dos encontros foi USD0,02350215, calculado de tokens retornados e tarifas configuradas; não é a cobrança da conta. A projeção de partida no relatório é um cenário de consumo e não um teto. Nenhum custo LLM é atribuído às partidas offline.
