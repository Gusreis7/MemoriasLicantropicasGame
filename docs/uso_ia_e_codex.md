# Uso de IA e programação guiada com Codex

Este documento separa os usos de IA no produto dos usos de IA no desenvolvimento. A IA não é uma fonte de verdade para as regras da investigação.

## IA em execução no jogo

O servidor usa o modelo configurado em `BEDROCK_MODEL`; o padrão atual é `qwen.qwen3-32b`, acessado pelo Bedrock Mantle. O modelo é usado para dar voz aos NPCs, escolher tons de entrega permitidos, circulação social, assembleia e textos editoriais. Credenciais entram por perfil AWS, credenciais padrão do ambiente ou bearer configurado; elas não são enviadas ao cliente do jogo.

O motor decide os fatos: sorteio, mortes, turnos, posições, presenças noturnas, álibis, observações, permissões de conhecimento, validade de provas e resultado de acusações. O modelo não recebe acesso direto ao Redis nem pode trocar a identidade da persona. Falha, atraso ou saída inválida em diálogos da mesa preservam a resposta factual canônica com tom direto. Veja [orquestração dos agentes](orquestracao_agentes.md), [mesa determinística](mesa_deterministica.md) e [consumo LLM](consumo_llm.md).

Uso e custo conhecidos são medidos pelo cliente da aplicação e ficam disponíveis no painel administrativo. Uma estimativa não substitui a fatura do provedor. Os testes comuns usam clientes controlados e bloqueiam HTTP externo; as simulações por API chamam o ambiente configurado de propósito, conforme [testes](testes.md).

## IA na produção visual

Parte dos sprites, cenários, retratos e variações foi produzida com `image_gen` integrado ao ambiente de desenvolvimento. Os prompts, arquivos de origem, hashes, referências de estilo e revisões ficam nos manifestos em `frontend/public/assets/` e em [direção de arte](art_direction.md). As imagens não definem papéis secretos, pistas ou resultados da partida.

Os sons distribuídos não são gerados por IA. Seus créditos e licenças estão em [créditos de efeitos open source](creditos_efeitos_open_source.md).

## Codex para programação guiada

Codex foi usado como parceiro de programação no checkout local. O usuário define objetivo, limites e autorização; o agente inspeciona o código, propõe e implementa mudanças dentro desse escopo, executa verificações e apresenta as evidências antes da integração. O humano permanece responsável por revisar o resultado e decidir sobre publicação, credenciais e alterações externas.

O processo usado neste projeto segue este ciclo:

1. Descrever a mudança e seu critério de aceite em linguagem direta.
2. Mapear código, documentação, scripts e testes afetados antes de editar.
3. Aplicar mudanças pequenas e rastreáveis; preservar alterações de terceiros no checkout.
4. Executar a menor verificação relevante, depois a suíte adicional justificada pelo risco.
5. Conferir o diff e links/formatos, registrar o resultado no Git e integrar apenas após os checks passarem.

Esse fluxo é compatível com o [guia oficial do Codex CLI](https://learn.chatgpt.com/docs/cli): trabalhar no repositório local, escolher permissões, revisar mudanças e usar os comandos de desenvolvimento já disponíveis no ambiente.

## Teste de programação guiada

O teste abaixo verifica a colaboração Codex + repositório; não avalia automaticamente inteligência do modelo nem substitui a revisão humana.

| Critério | Como verificar | Resultado desta documentação |
| --- | --- | --- |
| Escopo explícito | Pedido define o documento e seu conteúdo | Criado este documento, sem mudar a lógica do jogo |
| Referências verificáveis | Conferir caminhos, código e fontes citadas | Links locais validados; fonte oficial do Codex registrada acima |
| Mudança rastreável | Inspecionar `git diff` e o commit | Alterações limitadas à documentação e ao índice |
| Regressão evitada | Rodar a checagem proporcional | Validação de links locais e `git diff --check` aprovados |
| Decisão humana preservada | Nenhuma publicação ou alteração de conta sem instrução | Nenhum push, deploy ou alteração de credencial executado |

Para repetir uma tarefa guiada, abra o projeto em Codex, descreva o resultado esperado e os limites, peça a inspeção inicial e exija os comandos de validação no retorno. Antes de aceitar, leia o diff, rode os testes necessários e mantenha um checkpoint Git. O [guia oficial do Codex CLI](https://learn.chatgpt.com/docs/cli) recomenda checkpoints antes e depois da tarefa para facilitar a revisão e reversão.

## Limites de responsabilidade

Saídas de modelos podem estar erradas, incompletas ou inadequadas ao contexto. Nenhuma sugestão do Codex altera automaticamente uma conta AWS, publica código, expõe segredo ou valida uma mecânica de jogo sem os controles e testes do repositório. As permissões do ambiente e as aprovações explícitas continuam delimitando o que a ferramenta pode executar.
