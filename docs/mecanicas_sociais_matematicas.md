# Relações, fofocas e votos: modelo matemático

Esta implementação usa atributos dirigidos: a relação de Escobar com Bentinho não é a relação de Bentinho com Escobar. Não há consulta ao papel secreto nas funções de voto ou transmissão.

## Atributos e efeitos

Afinidade e confiança variam de −100 a 100; ressentimento, suspeita e lealdade de 0 a 100. Cada evento altera no máximo cinco pontos por atributo e possui causa UUID; repetir a causa não produz efeito. Os padrões de amizade, ciúme, proteção e antagonismo estão em `initial_relationships`.

Acesso a confidências é `100 * clamp(.25 + .35 confiança/100 + .25 afinidade/100 + .15 lealdade/100 − .30 ressentimento/100)`. Limiar 65 libera os segredos pessoais autorizados da ficha. Tratamento de Bentinho usa limiar 35; a confidência amorosa de Escobar e desejo de separação de Capitu usam 65. O fato de uma confidência estar disponível não obriga o personagem a contá-la.

Os tópicos autorais são semeados uma única vez por partida de maneira aditiva: casamento, ciúme, amizade Capitu/Escobar, seminário, insinuações de afeto, tratamento, separação, afeto privado e antagonismos Florença/Bacamarte/Rubião. Nenhum tópico fornece álibi ou presença numa noite específica. A paixão real de Escobar pertence apenas a ele; os outros recebem somente interpretações explicitamente incertas.

Ao receber uma acusação, o peso subjetivo é `clamp(.35 + .25 confiança_na_fonte/100 + .15 (ressentimento_alvo + suspeita_alvo)/200 − .15 max(0, afinidade_alvo)/100 − desconto_interpretação, .05, .8)`, com desconto de .15 para interpretação. Isso gera de 1 a 4 pontos de suspeita por raiz. Defesa pode reduzir o mesmo montante, com causa diferente, também apenas uma vez por raiz. O peso não certifica veracidade.

## Votação curta

API pura: `vote_scores(voter_id, suspect_id, relationships, proof_strength, argument_strength)` retorna scores do suspeito e de Floriano, ambos entre 0 e 1. As duas forças de entrada são limitadas a [0,1].

Credibilidade de Floriano: `C = clamp(.65 + .35 confiança_F/100 − .25 ressentimento_F/100)`.

Score acusado: `clamp(.10 + .72 prova + .18 argumento*C + .18 suspeita_A/100 + .12 ressentimento_A/100 − .14 afinidade_A/100 − .12 lealdade_A/100 − .08 confiança_A/100)`.

Score expulsar Floriano: `clamp(.03 + .28 max(0,−confiança_F)/100 + .24 ressentimento_F/100 + .24 suspeita_F/100 + .12 max(0,−afinidade_F)/100 + .20 (1−prova)(1−argumento) − .22 prova − .12 max(0,confiança_F)/100)`.

O acusado tem score zero para expulsar a si próprio. O orquestrador decide abstenção, margem, participantes, empate e maioria. A proposta inicial é score mínimo .50 e margem .08. Prova forte deve superar antagonismos moderados; acusação fraca feita por um detetive desacreditado pode voltar-se contra ele. Calibração e resultados de partidas ficam no relatório da exploração do integrador.

## Proveniência e fala natural

Toda cópia retém `root_id` e `parent_ids`; a circulação do mesmo boato não cria fonte independente. Repetição não cultiva suspeita indefinidamente. Conhecimento pessoal pode ser compartilhado apenas quando `can_share` libera para aquele interlocutor. Após uma confidência, a cópia permanece restrita (não vira informação pública automática).

O gerador recebe IDs de assuntos e produz uma fala natural. O motor não acrescenta mais citações literais nem “isso é um relato, não uma comprovação”. Uma guarda lexical conservadora exige pelo menos um termo significativo do assunto para aceitar seu ID; divergência é rejeitada, sem injetar texto não dito pelo NPC. Essa guarda não é um verificador semântico completo; avaliações reais de diálogo ainda são necessárias para medir paráfrases ruins ou coincidências lexicais.

O contexto distingue memória autoral, fala ouvida, fonte, interpretação e limiar de confidência. Os NPCs podem insinuar, acusar por ciúme, defender amigos e pedir ajuda. As vozes foram reformuladas para favorecer perguntas, desabafos e humor em vez de ressalvas repetidas.

## Compatibilidade e validação

O catálogo mantém `CONTENT_VERSION = 3`; contratos novos têm defaults e o SocialState conserva versão 1. Saves existentes recebem apenas tópicos e pares de relações ausentes; efeitos prévios não são zerados. A inicialização no worker é persistida com revisão/CAS; projeção antes do primeiro tick já conhece a perspectiva do personagem sem escrever estado durante leitura.

Os testes usam repositórios fake Redis e geradores programados, sem cobrança AWS. Verificam privacidade de confidências, fonte única, limites e idempotência, sensibilidade dos votos e possibilidade de expulsar Floriano, além de agenda e persistência reais do serviço social. Isso valida regras e integração; qualidade humana de fala livre depende das amostras com Qwen e não é provada por esses testes.

A extração de falas de Floriano também propõe reações afetivas com trecho validado: ajuda/apoio explícito dá +1 afinidade e +1 confiança; insulto explícito dá −2 confiança, +3 ressentimento e +1 suspeita; quebra conhecida de confidência dá −3 confiança e +4 ressentimento. Cada categoria tem uma causa por partida/NPC/dia, impedindo repetir a mesma tática no mesmo dia. Discordância simples não é classificada como insulto. Ganhos tão conservadores exigem calibragem do ritmo de confiança para partidas curtas; as fórmulas e limiares estão expostos para a exploração.
