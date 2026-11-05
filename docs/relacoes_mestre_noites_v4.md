# Relações direcionais, mestre de sessão e duas causas de morte

## Rede afetiva

A matriz fornecida pelo autor é a fonte de `knowledge/affects.py`. São 64 relações entre oito pessoas, incluindo Brás Cubas e a diagonal de sentimentos por si mesmo. Brás continua morto na abertura; suas relações são memória narrativa, não o tornam um NPC vivo ou sorteável.

Cada relação conserva um rótulo e intensidades independentes de 0 a 100. Amor, ódio e ciúme podem coexistir. Os valores autorais alimentam afinidade, confiança, ressentimento, suspeita e lealdade, usados pelo voto, tom e circulação de fofocas. Amor não concede confiança automaticamente. O jogador permanece com os vínculos anteriores; a tabela não especificou sentimentos por Floriano.

A direção importa: Escobar ama Bentinho, enquanto Bentinho sente ódio e ciúme por Escobar. Florença sente apatia por Bacamarte, conforme a nova matriz, mesmo que continue contestando a internação do pai na história. Relações podem mudar durante a partida; causas e deltas já obtidos são preservados na migração aditiva v 3 dos assuntos sociais. A diagonal não participa de votação, agenda de encontros ou punição coletiva.

Somente a linha do próprio personagem vai para sua instância de diálogo. Escobar pode ser motivado pelo amor sem que os demais recebam esse segredo: as condições anteriores de confidência continuam válidas. A matriz completa e as intensidades aparecem apenas no painel admin autenticado.

## Papéis do mestre

1. **Admissão:** avaliar fala própria, negação, hipótese e citação. A confirmação de vitória continua com o motor. Confissão civil não encerra a partida. Uma vítima de homicídio civil não é tratada automaticamente como vítima de um ataque do lobisomem para validar confissão.
2. **Relato útil:** avaliar o que efetivamente foi dito, com apoio conhecido, ou uma declaração própria literal de álibi/admissão. A saída pública ganha `useful: bool`, persistida no diálogo, histórico e relatos ouvidos. A interface usa dourado no chat e na aba Relatos do caderno. Útil significa digno de investigação, não verdadeiro nem suficiente para prender alguém. Texto do jogador e fala bloqueada não recebem esse destaque.
3. **Editor do Clarim:** `session_master/editorial.py` compõe manchete e texto breve a partir do resultado canônico. Custódia relata transformação na cela; confissão relata entrega; assembleia relata expulsão; derrotas recebem texto próprio. A edição matinal cita todas as vítimas da noite sem revelar o assassino ou atribuir todo homicídio à fera. A composição é determinística e não faz chamada extra ao modelo.

## Noites

- O lobisomem tem 65% de chance de atacar quando a noite anterior teve ataque. Após uma noite sem matar, o próximo ataque é obrigatório se houver vítima disponível. Uma noite em que o último civil estava protegido na cadeia também conta para o limite. Prender o lobisomem encerra o caso com transformação.
- Um civil vivo sorteado planeja matar outro civil vivo, distinto de si. Escolher outro civil evita remover o único lobisomem por um homicídio humano e deixar o caso sem solução. Brás, Floriano e o próprio autor ficam fora desse sorteio.
- Chances por noite do calendário:25%, 12,5%, 6,25%, 3,125%… São chances condicionadas a autor e alvo vivos, livres e presentes na cidade. Prisão impede tentativa; o calendário continua avançando. Após sucesso não há novo alvo.
- A resolução do lobisomem vem primeiro. Se ele mata o alvo planejado, o plano fica `frustrated`, com estresse 90. Se mata o autor, o plano é interrompido. Sem esse impedimento, o civil pode tentar o homicídio na mesma noite.
- Uma noite pode gerar zero, um ou dois crimes. Cada cena mantém assassino e causa privados, objetos do autor daquele crime e conhecimento limitado das testemunhas. Os registros de atividades consideram as duas cenas, sem criar duas posições incompatíveis para uma mesma pessoa.
- O civil culpado pode negar seus objetos ou mentir sobre o álibi. A fala pode admitir o homicídio; isso registra a descoberta sem vitória. Uma prisão de pessoa que não é a fera segue a prova noturna de licantropia e soltura, e a investigação continua.
- Uma semente privada persistida torna os sorteios noturnos estáveis por noite e canal. Reabrir uma partida, atualizar o navegador ou repetir a sincronização não refaz os sorteios. O público não recebe a semente, o plano, o estresse ou o contador de noites poupadas.

## Contratos e validação

As partidas novas usam a matriz atual e os assuntos autorais inicializados uma
vez. A inicialização preserva os deltas das relações atuais; não existe migração
entre matrizes de saves antigos. Os testes de relações/noites cobrem as 64
relações, probabilidades, sorteios, duas causas de morte, estresse e confissão civil.

O runner passivo anterior e seus artefatos foram retirados. Use a
[simulação atual de partidas completas](simulacao_partidas_refatoracao.md).

## Conferência da entrega

- Commit isolado da tarefa: 701 testes de backend e 44 de frontend passaram, com TypeScript e build Vite concluídos.
- Workspace compartilhado, incluindo as outras alterações já em andamento: 716 testes de backend e 56 de frontend passaram.
- Redis real em Docker: 60 testes de noites, persistência e ciclo passaram em namespaces exclusivos.
- Brave: 19 testes de fluxo passaram. O novo fluxo verifica o dourado na resposta, reabertura do histórico e aba Relatos do caderno; texto do jogador continua sem destaque.
- As 100 partidas de validação não consultam AWS. A voz gerada pelo modelo com a nova matriz não foi reavaliada por novas chamadas pagas nesta entrega.

A publicação local usa o workspace completo. As outras alterações de arte, horário, autenticação e relevância de diálogo foram preservadas e ficaram fora do commit desta funcionalidade.
