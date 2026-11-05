# Entrega da convivência e fofocas

Implementação do [plano](plano_convivencia_fofocas.md) nas frentes dos [contratos](contratos_convivencia_fofocas.md). A entrega mantém as fichas v3 e acrescenta um agregado social privado v1 por partida. Dados do jogo e trabalhos de arte de outras frentes são preservados.

## Comportamento entregue

- Cada par de mensagens confirmado entre Floriano e um NPC publica um registro em uma fila durável na mesma transação Redis do histórico. Repetir IDs não duplica a fila.
- O worker consome somente os pares confirmados na fila atual. Não importa transcrições antigas nem encontros privados NPC–NPC.
- O extrator processa até quatro pares consecutivos do mesmo NPC por chamada, preserva trecho literal, emissor, fonte alegada, dia e versões anteriores. Textos ambíguos ficam literais, fora da propagação automática. Tentativas bloqueadas não viram fofoca.
- O contexto de cada NPC recupera memórias próprias, relações e até três encontros anteriores, incluindo conversas sem uma alegação estruturada. O contexto não inclui transcrições privadas alheias.
- Afinidade, confiança e ressentimento são direcionais, com tendências derivadas das fichas. Acusações recebidas e versões contestadas podem gerar efeitos pequenos, limitados e rastreáveis. Nenhum efeito consulta a verdade secreta para decidir quem estava mentindo.
- A agenda escolhe pares por assunto, novidade, relação e participação. Há até quatro encontros/dia, nos slots60/120/180/240, com janela de15 segundos, até duas participações por NPC e intervalo mínimo de60 segundos para repetir o par.
- Viagens usam caminhos do catálogo; caminhadas dentro de um local também levam tempo. A posição de chegada só é confirmada após a duração prevista. Em trânsito o NPC fica indisponível. Um parceiro só aparece no snapshot público se também estiver visível.
- Cada encontro alterna até quatro falas. Propostas internas incluem fala, intenção e alegações citadas. A transmissão estruturada exige que a proposição e sua fonte tenham sido efetivamente pronunciadas. Negações, correções e interpretações conservam os vínculos com a origem.
- A abordagem de Floriano interrompe o encontro e preserva as falas já ditas. Noite, morte, prisão, prazo ou perda de reserva invalidam novas falas. Um resultado de inferência atrasado não pode confirmar efeitos após perder o direito de execução.
- Rumores continuam fora do cálculo de evidências e da decisão do delegado. A cadeia de fofoca não altera crimes, papel sorteado, presenças anteriores ou vitória.

## Integração e operação

O worker inicia e encerra junto com o lifespan da API. Partidas são descobertas pelo índice Redis existente; múltiplos processos disputam uma reserva por partida com token e fencing. O worker não mantém reserva do jogador durante inferência. Commits de fala, conhecimento e eventos são atômicos e revalidam o estado do jogo. O agendamento também verifica a fila dentro do CAS para não ignorar uma correção de Floriano recém-confirmada.

O relógio de dias/noites permanece sob o motor existente. Slots sociais antigos não são reconstruídos após ausência. Partidas encerradas com encontro pendente continuam descobertas apenas para liberar reservas e disponibilidade. Falha de inferência preserva o histórico e respeita o orçamento debitado antes da chamada.

| Configuração/limite | Valor |
| --- | --- |
| `SOCIAL_ENABLED` | `true`; `false` impede inferência social e libera encontros ativos, preservando memória |
| `SOCIAL_POLL_SECONDS` | 1 segundo; intervalo de descoberta/execução do worker |
| Inferências de fala | Até16 por dia/partida; saída de até400 tokens por chamada |
| Inferências de extração | Até8 por dia/partida; saída de até800 tokens por chamada |
| Timeout de inferência | 12 segundos |
| Prazo do encontro | Até40 segundos, limitado pelo anoitecer |

Chamadas usam a mesma configuração Bedrock e autenticação já existentes. A fala com o detetive mantém sua própria configuração e não conta na cota social. Sem credencial válida o worker falha de forma limitada; o restante do jogo continua acessível. Nenhuma chamada real de inferência foi necessária para a suíte desta entrega.

O jogo atualiza presenças pelo polling de mundo, preservando a caminhada prevista do jogador. Exibe conversas em andamento e permite interrompê-las pela abordagem. O caderno consulta `GET /api/v1/games/{id}/social/reports`, contendo somente falas que Floriano ouviu. O admin autenticado consulta `GET /admin/api/v1/games/{id}/social` e mostra encontros, falas, fontes, raízes e relações.

## Validação e limites

Atualização na evolução de interrogatórios: as primeiras chamadas reais demonstraram falhas de envelope JSON e de repetição literal. A extração aceita agora um único bloco JSON, valida cada alegação separadamente e preserva a validação de origem. Nos encontros, o motor acrescenta a citação e a fonte dos IDs selecionados à reação quando necessário; a transmissão só ocorre com essa fala final confirmada. O harness aplica verificações conservadoras de presença e fonte em português; essas regras não constituem verificação semântica completa. Resultados e falhas remanescentes estão no histórico Git anterior à limpeza; a integração atual está em [partidas completas](simulacao_partidas_refatoracao.md).

Há testes com Redis em memória e inferência simulada para extração, isolamento de atores, raízes e versões, circularidade, relações, cotas, caminhadas, viagens, fase, abordagem, worker, recuperação e transações. O fluxo integrado cobre Floriano → Capitu → Virgília → retorno ao detetive, incluindo cobrança, negação e ausência de alterações nos fatos do caso. A projeção pública e a exigência de sessão no endpoint administrativo são verificadas separadamente.

O runtime restrito desta sessão apresentou uma falha de despertar do threadpool AnyIO, reproduzida fora da aplicação. Para a suíte HTTP, foi usado um plugin temporário em `/tmp/ml_async_heartbeat.py`, que mantém um timer no event loop inclusive durante o teardown. O código da aplicação e do repositório não recebeu esse contorno ambiental.

O modelo continua sendo responsável por interpretar frases e produzir prosa. Trecho literal validado não prova interpretação semântica correta. A primeira versão exige repetição explícita da proposição e da fonte para propagar conhecimento; não habilita fabricação arbitrária de alegações sem origem. Falas sem alegações citadas continuam no histórico do encontro, mas não criam automaticamente um relato estruturado no próximo NPC. Segredos têm guarda e projeção restrita; paráfrases indevidas continuam exigindo avaliação com modelo real.

A importação inicial materializa o histórico da partida em uma transação. Isso atende ao tamanho atual do protótipo; histórias muito grandes exigirão importação paginada com checkpoints. A cota de extração continua valendo para o histórico importado. NPCs com falas pendentes aguardam o processamento antes de novos encontros, enquanto os demais continuam elegíveis.

O próximo passo de calibração é medir com modelo real a fidelidade da extração, naturalidade das citações, qualidade do tom e incidência de divulgação indevida antes de ampliar distorções e reduzir a exigência de citação literal.

Resultado da integração: **444 testes backend aprovados**, **30 testes TypeScript aprovados** e **build frontend aprovado**. O build mantém o aviso existente de tamanho do bundle Phaser. O executável de testes de navegador deixa a agenda social desativada para preservar os cenários de investigação com posições fixas; o fluxo social usa seus próprios testes integrados com relógio e respostas controlados.
