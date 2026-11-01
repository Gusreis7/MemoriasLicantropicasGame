# Relógio, noites e persistência

O relógio autoritativo fica em `modules/turns`. Cada dia dura300 segundos reais;
a noite dura8 segundos, sem ações do jogador. As durações são injetáveis somente
na construção do serviço para testes, nunca por uma rota pública.

`TurnService.sync` usa a mesma reserva Redis de movimento/conversa. Requisições
concorrentes recebem conflito ou o estado já resolvido, sem duplicar eventos.
A sincronização é lazy: não exige worker, e o navegador consulta o agregado a
cada segundo. Na retomada, vencimentos são processados em ordem a partir dos
deadlines persistidos, até o fim da partida. O GET que sincroniza pode escrever
uma fase vencida; consultas sem vencimento não regravam o estado.

À noite, o lobisomem mata um civil vivo elegível; a preferência segue sua ficha.
Detido inocente não pode ser vítima naquela noite e é solto pela manhã. Se só ele
restar, o jornal noticia ausência de morte. O preso lobisomem se transforma, a
cidade o expulsa e o jogo termina em vitória sem outra morte naquela noite.
Se todos os civis morrerem, o resultado é derrota. O papel nunca é ressorteado.

Cada manhã produz edição do Clarim do Rio e reposiciona Floriano na Praça Verde,
x160, voltado à direita e parado. A sequência de movimento é preservada e a
revisão do mundo avança; comandos anteriores não voltam a mover o jogador.

## Transação e recuperação

`RedisTurnRepository.commit` observa `investigation`, `state`, `world` e `events`
da mesma partida. Confere revisões, identidade, sorteio imutável e tipo da lista
de eventos antes de `MULTI`. Atualiza agregado, vida/status, mundo e eventos em
uma única transação. Eventos reais de morte usam `character.killed` e origem
`rules`; mensagens do LLM não criam mortes. O bootstrap de partida inclui o novo
agregado na transação já existente, mantendo os três eventos iniciais.

Partida anterior sem agregado começa no instante de sua primeira sincronização,
com evento `investigation.initialized` e sem sorteio ou perda de conversas. Estado
corrompido gera falha sanitizada. Um serviço reconstruído retoma os mesmos
deadlines; datas não são recalculadas com base em recarga da página.

`require_day_locked` pressupõe que o chamador já detém a reserva. Sincroniza e
recusa fases sem interação. `assert_dialogue_open` apenas lê e compara o relógio,
sem reserva recursiva: o harness usa essa checagem depois da inferência e antes
de persistir um diálogo que possa ter atravessado o fim do dia.

`act` executa uma transição diurna pura, valida que ela não alterou relógio,
fase ou resultado, atribui a revisão no servidor e grava os eventos juntos.
Uma ação idempotente que retorna o mesmo estado sem eventos não gera escrita.

Os testes de `tests/test_turns.py` usam relógio controlado e armazenamento isolado,
sem AWS. Cobrem fronteiras de300/8 segundos, crime e pistas, prisão correta e
incorreta, ausência de morte, derrota, catch-up, concorrência, reinicialização,
chave de eventos inválida e recusa de diálogo após o deadline.
