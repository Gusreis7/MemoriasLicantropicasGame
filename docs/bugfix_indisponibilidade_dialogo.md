# Bugfix — indisponibilidade de resposta e recuperação de histórico

## Diagnóstico verificado

Mensagem relatada: “A resposta não pôde chegar agora. Confira o histórico antes de reenviar sua pergunta.”

O frontend substituía qualquer erro503 por esse texto, incluindo falhas de persistência e operações fora do diálogo. No ambiente em execução, quatro POSTs de mensagens retornaram503; consultas de mundo e investigação retornavam200. A API estava com `AWS_PROFILE` ausente e sem bearer Bedrock. O perfil `terraform` do host conseguia gerar um token. A saúde do processo não verificava autenticação de inferência.

Havia também um erro no fluxo de confirmação: POST bem-sucedido seguido de falha no GET de histórico era apresentado como falha de envio, apesar de a resposta já ter sido confirmada. Isso podia incentivar uma pergunta duplicada.

## Correção no ambiente servido

Foi reaplicado somente o overlay AWS à API, com `docker compose -f compose.yaml -f compose.aws-local.yaml up -d --no-deps api`. Redis e seus volumes não foram recriados. Dentro do container, a geração de token passou a funcionar.

Uma chamada real curta ao modelo foi bem-sucedida. Em seguida, uma conversa real com Capitu percorreu criação, abordagem, inferência e persistência em um namespace temporário exclusivo. O histórico terminou com duas mensagens. Os dados temporários foram removidos, sem usar nem alterar a partida do jogador.

O runtime servido usa catálogo v2; o workspace contém a evolução para v3 e convivência social. A imagem foi preservada nesta correção operacional, evitando rejeitar as partidas atuais com409. As mudanças de código abaixo pertencem ao próximo build compatível com a versão de conteúdo adotada.

## Correções de código

| Frente | Mudança |
| --- | --- |
| Diagnóstico backend | `LLMUnavailableError` tem código público restrito a uma lista segura. Autenticação ausente/indisponível/recusada, cota, timeout, modelo indisponível, formato inválido e truncamento são distintos. |
| Resposta HTTP | Erros do modelo retornam `detail` seguro e `code`. Falhas Redis mantêm seu contrato original. Nenhum payload de provedor, credencial, perfil privado ou prompt é exposto. |
| Observabilidade | Log registra somente código seguro de indisponibilidade; startup sem chave e sem perfil emite indicação de configuração ausente. |
| Configuração local | O configurador e o exemplo de ambiente orientam o uso do overlay quando a autenticação depende do perfil AWS. |
| Interface | `ApiError` preserva o código, e o frontend mostra o detalhe específico em vez de converter qualquer503 em falha genérica de diálogo. |
| Confirmação de envio | Sucesso do POST é confirmado antes de atualizar o histórico. Se o GET falhar, a resposta recebida continua visível e o rascunho é limpo. |
| Resposta perdida | Após falha de envio, uma leitura procura um par novo com a pergunta enviada, comparando IDs com o histórico anterior. Um par encontrado é tratado como confirmação. |
| Incerteza | Sem confirmação, o texto é preservado. Se o histórico também falhar, a interface explica a incerteza e mantém o rascunho isolado por partida/conversa. Não há reenvio automático. |

A recuperação pelo histórico não equivale a idempotência da requisição inteira: abas concorrentes continuam sujeitas às reservas existentes. Um erro de rede pode acontecer enquanto o servidor ainda trabalha; ausência de resposta na primeira leitura não autoriza presumir que a pergunta jamais será salva.

## Como evitar recorrência

Para autenticação por perfil no Docker, use `make setup` na primeira subida e `make up` nas seguintes. Esses comandos selecionam o overlay AWS quando o perfil local está disponível. Ao recriar apenas a API manualmente, inclua esse overlay. `docker compose up` sem ele só atende inferência se houver bearer explícito configurado. API e Redis saudáveis não comprovam disponibilidade do modelo.

O overlay mantém a fonte do perfil montada somente para leitura. Se a sessão do container expirar e o login do host já tiver sido renovado, o provider copia apenas arquivos regulares mais novos para o cache temporário privado e repete a geração do token uma vez. Links simbólicos são ignorados. Isso permite que a próxima tentativa de diálogo se recupere sem reiniciar o Redis nem alterar a partida.

Se o perfil expirar, renovar a autenticação AWS no host e executar o launcher novamente para atualizar a cópia temporária das credenciais. Não apagar volumes nem recomeçar uma partida para tratar autenticação. Para falhas de inicialização do Redis, siga o [guia de execução](execucao_docker.md#diagnostico).

## Validação

Testes simulados cobrem classificação dos erros, sanitização de HTTP/logs, ausência de chamada ao provedor quando faltam credenciais, ausência de meio diálogo salvo e liberação das reservas após falha. Testes frontend cobrem POST confirmado com GET falho, confirmação recuperada do histórico, rascunho preservado, estado incerto e ausência de reenvio automático. A validação real do ambiente foi feita separadamente com dados temporários.

Resultado: **465 testes backend aprovados**, **38 testes frontend aprovados** e **build frontend aprovado**. A suíte HTTP usou o timer temporário do executor descrito na entrega de convivência, sem alteração da aplicação para contornar o ambiente. A chamada real simples retornou11 tokens de saída; a conversa real com Capitu retornou uma fala de280 caracteres e confirmou duas mensagens no histórico.
