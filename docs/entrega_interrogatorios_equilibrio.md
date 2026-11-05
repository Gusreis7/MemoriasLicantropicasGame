# Entrega de interrogatórios, confissão e consumo

Implementação do [plano e divisão de responsabilidades](plano_interrogatorios_equilibrio.md), com três subagentes e integração da interface/harness pela coordenação. A branch de trabalho é `feat/interrogatorios_simulacoes`. A entrega incorpora a convivência e as correções de diálogo que já estavam no diretório de trabalho, preservando os arquivos e consolidando sua integração com o catálogo v3.

## Mecânicas e informação

Todos os civis procuram identificar a ameaça e sobreviver, preservando interesses e intimidade. Conhecimento e disposição variam por personagem. Interrogatórios registram local, companhia e atividade por dia/período. As observações são de instantes conhecidos, sem prometer álibi para a noite inteira; presença atual não reconstrói o passado. Repetir a pergunta retorna a versão original. Presos, mortos e viajantes não se tornam testemunhas de lugares onde não podem estar.

Confrontar exige selecionar registros do caderno, incluindo uma versão do alvo, objetos corroborados e versões inconsistentes. Pressão e dificuldade são privadas e variam por persona. Uma recusa não confirma inocência nem culpa. A confissão validada encerra o caso em vitória e entrega o lobisomem ao delegado; a outra vitória continua sendo prisão seguida de transformação noturna. O lobisomem vence se sobreviver à investigação até não restarem civis. As regras e os contratos estão em [interrogatorios.md](interrogatorios.md).

A interface oferece **Interrogar e confrontar versões** dentro da conversa. O caderno apresenta álibis, observações e confrontos; o desfecho diferencia confissão e prisão. O admin identifica quem confessou como sob custódia, sem confundir essa situação com expulsão após transformação.

## Convivência e modelo real

Encontros limitados entre NPCs, viagens, interrupção por Floriano e memórias com origem continuam separados dos fatos do crime. Interrogatórios próprios e observações autorizadas também alimentam a conversa social. Uma inferência não cria prova, prisão, visita passada ou vitória.

A avaliação real encontrou falhas de JSON e de reprodução literal. O parser aceita objeto puro ou um único bloco JSON cercado, rejeita chaves duplicadas/prosa extra e descarta alegações estruturalmente inválidas individualmente. O modelo escolhe relatos conhecidos e escreve a reação; quando necessário, o motor acrescenta citação e fonte canônicas à fala antes da persistência e transmissão atômicas. Pedidos maliciosos não tornam dados privados compartilháveis. Guardas conservadoras também bloqueiam padrões conhecidos de presença ou fonte inventada. Isso reduz erros observados sem constituir prova de correção semântica para qualquer paráfrase.

## Uso e custo

O admin autenticado acompanha chamadas, tokens conhecidos de entrada/saída, tempo e subtotal USD por partida, finalidade e modelo. Inclui inferências descartadas pela aplicação após resposta do provedor. Contagens ausentes e períodos anteriores à medição ficam explicitamente desconhecidos. Tarifas são fixadas por chamada, configuráveis e vinculadas ao modelo/região. Não se presume crédito promocional nem cobrança efetiva. Ver [consumo_llm.md](consumo_llm.md).

## Avaliação e próximos experimentos

O relatório retirado deste checkout, disponível no histórico Git anterior à limpeza, documenta dez partidas com políticas que só consultam dados públicos, além de rodadas narrativas reais antes/depois das correções. Os sete personagens aparecem como culpados nas partidas de cobertura; foram exercitadas confissão, prisão correta, prisão inocente seguida de soltura, acusação insuficiente e passividade.

O resultado mecânico final foi sete vitórias do detetive e três do lobisomem. É uma amostra dirigida de cobertura. Custos de leitura são sintéticos e otimistas, enquanto a latência do modelo é medida separadamente; portanto não é uma estimativa de equilíbrio para jogadores humanos. Bacamarte resistiu à política de confissão até a derrota, embora a rota de prisão permaneça disponível.

Experimentos seguintes: medir tempos humanos; comparar custos de abordagem/exame; diversificar a política de encobrimento e reconhecimento; medir robustez narrativa por personagem e sotaque/paráfrase de pergunta; comparar confiança de fontes independentes com recirculação da mesma origem. A política antiga de negação de objetos próprios do lobisomem ainda oferece sinal previsível e precisa ser calibrada junto com as pistas, sem mudar regras apenas para obter uma taxa desejada nesta amostra.

## Validação e execução

- 515 testes Python aprovados com Redis real isolado; 39 testes TypeScript aprovados e build Vite/TypeScript aprovado.
- Sete fluxos de navegador executados no Brave, incluindo interrogatório, caderno, seleção de elementos e desfecho por confissão; o teste da interface usa contrato simulado e os testes backend validam o motor correspondente.
- Docker preserva o volume Redis e a autenticação AWS local. Jogo em7077, admin em7078 e API em7079. O catálogo atual é v3; partidas antigas incompatíveis continuam preservadas, mas exigem criar um caso novo para jogar com este conteúdo.
- O plugin temporário de heartbeat já documentado foi usado no executor pytest deste ambiente; ele não faz parte da aplicação ou imagem de produção.

A verificação do build Docker no Brave recebeu e persistiu uma conversa real, registrou um interrogatório e confirmou tokens conhecidos e custo positivo no endpoint autenticado de consumo. A última correção de memória literal foi validada pelas regressões de inversão de sujeito e pelo rebuild da API; não se executou uma quarta rodada remota completa.
