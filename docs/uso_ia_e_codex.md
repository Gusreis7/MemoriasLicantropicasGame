# Como usei IA no projeto

## Nos personagens

Usei IA para dar voz aos NPCs e compor trechos narrativos. Nas conversas da
mesa, o modelo escolhe entre formulações permitidas; ele também participa dos
encontros entre personagens, da assembleia e dos editoriais.

Desenvolvi e testei essa parte usando **créditos da AWS**. O modelo principal é
o **Qwen3-32B (`qwen.qwen3-32b`)**, acessado pelo **Amazon Bedrock Mantle**,
com `BEDROCK_MODEL` disponível para selecionar um modelo nesse serviço.
**Não implementei, por enquanto, uma opção de inferência com LLMs locais**:
Ollama e LM Studio não fazem parte do fluxo de execução atual. Para reproduzir
as conversas é preciso acesso próprio ao serviço, sujeito a cobrança.

Mantive as regras da investigação no servidor: sorteio, mortes, posições,
encontros, álibis, permissões e resultados de acusações. Assim, uma fala gerada
não cria uma prova nem muda o que aconteceu na partida. O modelo consulta apenas
as informações liberadas para cada personagem. O funcionamento está descrito em
[NPCs e mestre da mesa](orquestracao_agentes.md).

As credenciais ficam no servidor, não no navegador. O painel permite acompanhar
o consumo e as estimativas de custo, que não substituem a cobrança registrada
na AWS. Os testes automáticos usam modelos controlados; avaliar a qualidade das
falas do Qwen3-32B exige uma execução separada e pode consumir créditos.

## Nas imagens

Gerei parte dos cenários, retratos e sprites com a ferramenta `image_gen`.
As referências, os prompts e as revisões ficam nos manifestos em
`frontend/public/assets/`. Os sons vieram de outras fontes, reunidas nos
[créditos](creditos_efeitos_open_source.md).

## Na programação com Codex

Desenvolvi o jogo ao longo de sessões de programação guiada com Codex. Comecei
pelas mecânicas e pelo comportamento que queria ver no jogo. A partir disso,
usei a ferramenta para investigar o código, discutir alternativas, preparar
planos e implementar as mudanças.

Trabalhei com **desenvolvimento assistido por IA, orientado por especificações**,
inspirado em [Spec-Driven Development (SDD)](https://github.com/github/spec-kit/blob/main/spec-driven.md).
Antes das mudanças maiores, detalhei regras, limites e critérios de aceite.
Essas definições orientaram a implementação e foram sendo refinadas conforme
eu testava o jogo e encontrava problemas.

Não adotei um framework específico de SDD. Usei as conversas e os planos de
execução para organizar o trabalho. Nas etapas maiores, também usei subagentes
com tarefas e responsabilidades delimitadas, seguidos de integração e revisão.

Meu fluxo foi definir o resultado esperado, investigar os arquivos envolvidos,
revisar o plano, implementar e conferir o resultado com testes e uso da aplicação.
Questões como álibis inconsistentes, atraso na movimentação e falhas no deploy
voltaram para esse ciclo até receberem os ajustes necessários.

O projeto também foi uma forma de experimentar o Codex na programação guiada.
Usei o diff, os testes e a execução do jogo para avaliar as mudanças, mantendo o
histórico no Git para comparar resultados e reverter quando necessário.
