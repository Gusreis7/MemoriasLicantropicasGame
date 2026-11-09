# Diálogo da mesa: voz e limite de conhecimento

A mesa determina quais informações cada personagem conhece e pode revelar. O
modelo participa da apresentação, sem modificar origem, lugar, noite, companhia,
status do álibi ou consequência probatória.

O turno distingue informação nova, assunto desconhecido e assunto esgotado.
Sem conhecimento pertinente, o NPC admite não saber ou não lembrar e pergunta se
podem falar de outra coisa. Declarações já entregues ao mesmo interlocutor não
são apresentadas como novidades. Pedidos explícitos para repetir são permitidos;
fatos novos e períodos diferentes continuam disponíveis. A busca de fofocas filtra
os fatos já ouvidos antes de limitar a resposta, evitando encerrar um assunto que
ainda possui informações.

A apresentação usa saída estruturada nativa do LangChain/Pydantic. A composição
mantém segmentos factuais controlados pela mesa; o LLM escolhe a formulação e o
enquadramento da persona. Reformulação livre de fatos arbitrários não oferece
garantia de equivalência semântica e não constitui a autoridade do jogo. Falhas de
formato, tentativas de alterar fatos e indisponibilidade devem preservar a fala
canônica. Nenhum novo depoimento ou fonte independente nasce da reformulação.

A avaliação ao vivo depende de credenciais AWS válidas. Nesta manutenção, o perfil
local `terraform` retornou login expirado; testes com inferência simulada não devem
ser apresentados como avaliação narrativa real do Qwen.

O plano editorial é um contrato tipado interno com índices de abertura, variante
por fato e fechamento. Não há campo de texto livre no plano do modelo. O motor
recalcula as variantes autorizadas a partir dos registros canônicos e confere a
fala resultante antes de registrar os depoimentos; uma proposta não pode trocar
pessoa ou ampliar a cobertura de um álibi parcial. O outbox preserva o plano para
que a mesma verificação funcione na reconciliação da troca.

Declarações de conhecimento incluem os IDs de origem na identidade, mantendo a
mesma raiz probatória. Uma correção nova pode reabrir o assunto, sem contar como
mais uma fonte independente. A reformulação não altera os dados que aparecem
no caderno ou que o delegado usa para avaliar o caso.

## Validação desta alteração

Passaram 102 testes de mesa/entrega/esgotamento, contratos nativos e segurança
básica. Cobrem plano válido, tentativa de fornecer texto factual livre, perda de
fatos, índices inválidos, cobertura parcial, indisponibilidade, timeout,
recapitulação, fofocas restantes e correção nova da mesma raiz.

A execução ampliada de `pytest tests` parou com quatro falhas de HTTP 429 em
`test_case_integration.py` (131 testes passaram antes da parada). O caso Bentinho
foi reproduzido em uma cópia limpa do HEAD anterior e também falhou com 429;
essa bateria histórica não está declarada aprovada. O alvo padrão do pytest no
checkout contém apenas três arquivos, portanto não representa a suíte completa.

Nenhuma inferência Qwen foi executada: o perfil AWS estava expirado. As escolhas
de voz, latência e variedade reais ainda precisam dessa avaliação ao vivo.
