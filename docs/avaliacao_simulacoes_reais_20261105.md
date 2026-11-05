# Avaliação real após a correção dos diálogos — 05/11/2026

Foram executadas cinco amostras por HTTP contra a aplicação local, com Qwen/Mantle
real para Floriano e os NPCs. O servidor manteve relógio, sorteio e autorização
normais. Não houve política fixa, teletransporte ou resultado injetado.

| Etapa | Sessões | Decisões executadas | Diálogos | Encerramento da avaliação |
| --- | ---: | --- | ---: | --- |
| Contrato anterior, repetição inicial | 2 | 9 / 8 | 0 | `invalid_schema` |
| Contrato anterior, diagnóstico dos argumentos | 2 | 11 / 17 | 0 | `invalid_schema` |
| Contrato explícito por ação | 1 | 41 | 2 | `invalid_tool_response` |

Nenhuma partida terminou pelo motor. As sessões com erro não contam como derrota;
suas partidas continuaram ativas no servidor. A amostra não permite avaliar taxa
de vitória nem equilíbrio, e os sorteios diferentes impedem uma comparação causal
de desempenho. O [relatório compacto](reports/live_after_dialogue_fix.json) registra
os contadores e as fontes locais.

## Correção encontrada na simulação

O DTO anterior tinha apenas `action` obrigatório no schema enviado ao modelo.
Campos como `npc_id`, `crime_id` e `x` eram exigidos por validação interna depois
da geração. As chamadas reais retornaram, por exemplo, `approach` sem `npc_id`
e `move` sem `x`. O modelo não via essas exigências no contrato nativo.

`FlorianoAction` agora contém `decision`, uma união discriminada por `action`.
Cada alternativa declara seus argumentos obrigatórios no schema. Argumentos
ausentes ou extras continuam rejeitados; nenhum ID nem ação é preenchido pelo
runner. Testes verificam tanto o schema publicado quanto a validação dos dados.

## Comportamentos observados

Na amostra com o contrato explícito, Floriano executou 19 buscas, oito viagens,
seis abordagens, três movimentos, três observações e dois diálogos. Houve 23
recusas de ação por autorização/distância, ausência do NPC ou conflito de estado.
Insistiu em buscar pistas fora do alcance e alternou locais com pouco progresso.
Terminou sem objetos, depoimentos, acusações ou conquistas nessa partida.

Rubião e Capitu responderam às perguntas formuladas pelo agente. As duas falas
foram registradas como `accepted`, sem fallback. Uma pergunta de Floriano misturou
português com caracteres chineses, apesar da instrução para conversar em português.
São limitações observadas do agente, sem correção automática de suas escolhas.

O bloqueio final foi de protocolo: depois de 41 decisões, duas tentativas não
produziram a ferramenta esperada. `required` e instrução explícita melhoraram o
fluxo, mas não garantem emissão válida em toda chamada. O runner conservou o erro
em vez de aceitar texto livre ou escolher uma ação substituta.

## Consumo e evidências

Nas cinco amostras foram registradas 102 chamadas de Floriano. O custo estimado dos
tokens conhecidos foi US$ 0,10131915. A auditoria da última sessão registrou nove
chamadas do servidor e US$ 0,00654870; total conhecido nas fotografias: aproximadamente
US$ 0,108. O consumo posterior da convivência das partidas ativas não está incluído.

Os eventos completos das três últimas sessões estão em:

- `artifacts/simulations/live-after-dialogue-fix-diagnostic/`
- `artifacts/simulations/live-explicit-actions-1/`
- `artifacts/simulations/floriano-invalid-proposals.jsonl`

Os eventos temporários do primeiro lote não estavam disponíveis na cópia posterior;
seu resumo do terminal foi preservado separadamente no relatório. As execuções
seguintes gravaram diretamente no checkout para persistirem fora do container.

Após a alteração do contrato: **835 testes e sete subtestes passaram**. A próxima
avaliação ampla precisa separar tolerância a decisões de protocolo inválidas,
planejamento espacial, repetição sem progresso e qualidade linguística de Floriano.
