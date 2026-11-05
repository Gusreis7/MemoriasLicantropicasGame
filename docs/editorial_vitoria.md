# Editorial de vitória

Ao vencer por confissão, transformação na cela ou assembleia (incluindo votação encerrada pelo relógio), o mestre da sessão usa seu cliente de modelo para escrever uma breve opinião na edição final de O Clarim do Rio. O artigo é assinado por Leonidas Soares, personagem fictício e diretor do jornal.

O texto é precedido por fatos do motor: identidade do lobisomem, participação de Floriano no desfecho e nomes e quantidade das vítimas atribuídas à fera. Crimes de autoria humana ficam fora dessa atribuição. O modelo recebe somente esse resumo e contagens de vestígios recolhidos e depoimentos; não recebe falas do jogador ou segredos dos demais personagens.

A edição é salva junto da transição de vitória. Consultas posteriores reutilizam o artigo salvo. Se o modelo falhar ou entregar texto vazio, excessivo ou rejeitado pelo guard, uma opinião de reserva acompanha os mesmos fatos e assinatura. A geração acrescenta uma chamada ao modelo mestre na conclusão da partida; o texto opinativo gerado está sujeito às limitações de fidelidade do modelo.

Validação: `pytest -q tests/test_victory_editorial.py tests/test_turns.py tests/test_session_master_v2.py tests/test_relationships_nights_master_v4.py`.
