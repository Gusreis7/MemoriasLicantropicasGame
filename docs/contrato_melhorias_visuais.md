# Contrato de melhorias visuais e inventário

Esta entrega divide três mudanças independentes em branches próprias, derivadas de `develop`:

| Branch | Escopo | Contrato de saída |
| --- | --- | --- |
| `feat/delegado-personagem-cela` | Personagem completo do delegado na cela | Asset transparente de corpo inteiro e cena da custódia com o delegado sentado/posicionado atrás da mesa. Não usar retrato como substituto de personagem. |
| `feat/itens-pixelart-coleta` | Arte dos itens e pilha no inventário | Itens reconhecíveis em pixel art; coleta repetida do mesmo `item_id` exibe uma pilha com quantidade, sem apagar os UUIDs individuais de evidência usados em depoimentos e acusações. |
| `feat/jornal-retratos-mortes` | Edição matinal do Clarim | Edição inclui retrato da vítima em preto e branco e número acumulado de mortes suspeitas calculado no servidor a partir das mortes da partida. |

## Integração

- As branches devem partir de `develop`, fazer commits próprios e não modificar arquivos fora do escopo atribuído sem avisar.
- A integração é feita pela branch principal em ordem: custódia, itens/inventário e jornal. Conflitos em arquivos compartilhados devem ser resolvidos preservando todos os contratos acima.
- Cada agente reporta hash do commit, arquivos alterados e eventuais migrações de contrato. O agente não executa testes nem reinicia Docker.
- Após a revisão e integração, a aplicação é reconstruída e reiniciada uma única vez.

## Contratos de dados

- `item_id` identifica a espécie do objeto e é a chave de agrupamento visual. Evidências diferentes mantêm IDs próprios e continuam individualmente referenciáveis por depoimentos, confrontos e acusações.
- A contagem de mortes é derivada do estado autoritativo do servidor; o cliente não estima nem persiste essa contagem.
- O retrato da vítima mantém o identificador público do personagem e recebe tratamento monocromático na apresentação do jornal.
- A cena da cela usa um asset de personagem no espaço da delegacia; retratos destinados à interface de diálogo não são assets de cenário.
