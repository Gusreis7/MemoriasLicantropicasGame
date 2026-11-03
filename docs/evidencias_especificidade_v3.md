# Evidências v3: marca pessoal, vínculo com a cena e corroboração

## Problema observado no código anterior

O primeiro crime deixava um comum e um singular. A acusação somava 1 e 2 pontos mais um bônus automático de 1; dois tipos ligados por um único depoente já atingiam 4 e autorizavam prisão no primeiro dia. Confirmar propriedade acabava substituindo investigar o ataque.

## Peso e condições

A nova avaliação recebe apenas o estado de investigação e o dossiê selecionado. Não lê `GameState.role`, `killer_id`, `deposited_by` ou `Testimony.truthful`.

- Cada **comum** vale 0,25. Todos os comuns, juntos, têm teto de 0,5.
- Cada **singular** vale 1. O conjunto dos singulares tem teto de 2.
- Cada **exclusivo** vale 3. Um tipo não pontua novamente por aparecer em outra cena ou ser anexado várias vezes.
- Corroboradores externos distintos dão 0,5 cada, até 1. O próprio acusado não é uma segunda fonte. Repetir a mesma testemunha sob vários registros não cria independência.
- Uma contradição entre álibis já declarados no caderno pode dar 0,75. Só conta observação declarada como presenciada, para o mesmo dia e período; não se usa a verdade oculta das atividades.

Custódia exige pontuação de pelo menos **5**, pelo menos **dois tipos** ligados ao acusado, um **exclusivo examinado** com vínculo físico com a cena e **duas fontes externas**. Uma fonte externa e uma contradição pública de álibis constituem uma rota alternativa, para dar valor à conversa natural.

O delegado informa quais elementos faltaram: variedade, exame de marca pessoal, corroboração ou especificidade. Não revela o proprietário verdadeiro nem o culpado. A hipótese ainda precisa da resolução da noite.

## Exame do objeto

`rules.inspect_evidence(state, evidence_id, now) -> CaseTransition` exige objeto real e recolhido. O primeiro exame produz um evento `evidence.examined`; repetir retorna o mesmo estado sem novo evento.

Para exclusivos, o texto descreve assinatura de manufatura/reparo e um vestígio físico compatível com a luta na cena. Isso estabelece um vínculo material; não dá o nome de quem deixou o objeto. O reconhecimento por testemunhas continua necessário. Objetos comuns e singulares também podem ser examinados, mas o exame não promove sua raridade nem aumenta seu peso.

Contrato interno `Evidence`: `examined=False`, `inspection_text=None`, `crime_link_verified=False`. A API deve projetar apenas os dois primeiros novos campos e nunca `crime_link_verified` ou `deposited_by`. Um exemplar examinado pode servir à seleção da mesma espécie empilhada; cópias não multiplicam pontos.

## Objetos pessoais

Cada pessoa conserva os cinco IDs anteriores e ganha dois exclusivos, totalizando **sete apetrechos**: três exclusivos, um singular e três comuns. Os nomes e marcas seguem as fichas autorais; nenhum objeto contém o papel sorteado.

| Pessoa | Exclusivo anterior | Novos exclusivos |
| --- | --- | --- |
| Bentinho | Chave com medalhão Santiago | Rosário de contas irregulares (`rosario_seminario`); papel de carta com selo Santiago (`carta_santiago`) |
| Capitu | Estojo de cartas com olho de cobre | Pente com olho de cobre (`pente_olho_cobre`); sinete da lua partida (`sinete_lua`) |
| Escobar | Prendedor de gravata em âncora | Caderneta de capa azul (`caderneta_seminario`); abotoadura de esmalte esmeralda (`abotoadeira_esmeralda`) |
| Rubião | Relógio com gravação Quincas | Abotoadura de sol dourado (`abotoadeira_sol`); medalhão de Quincas (`medalhao_quincas`) |
| Virgília | Leque com monograma VN | Camafeu de iniciais VN (`camafeu_vn`); frasco de violeta lapidado (`frasco_violeta`) |
| Florença | Broche de andorinha | Dedal de andorinha (`dedal_andorinha`); fivela da folha dobrada (`fivela_manifesto`) |
| Bacamarte | Lente de armação hexagonal | Estilete de cabo verde (`estilete_casa_verde`); selo hexagonal da Casa Verde (`selo_casa_verde`) |

## Disponibilidade e justiça

O crime inicial preserva comum + singular, sem uma assinatura pessoal que permita encerrar a investigação logo no primeiro dia. A partir da segunda manhã os crimes deixam comum + um dos três exclusivos da pessoa culpada. A escolha varia de forma estável por partida e gira entre as peças em noites seguintes. A regra seleciona por tipo no catálogo, sem depender de índices mágicos de inventário.

Cada morador passa a conhecer os objetos de três outros moradores, em vez de dois. Assim o proprietário tem três observadores externos; após a primeira morte noturna ainda existem pelo menos dois. Depoimentos já obtidos de alguém que venha a morrer continuam válidos. Nenhum segredo amoroso é requisito para prender ou vencer. Demorar várias noites ainda reduz as oportunidades de ouvir testemunhas, como parte do risco da investigação.

Reconhecimentos de peça pessoal apontam um nome e uma marca concreta. Desconhecimento oferece um próximo contato vivo por tipo do objeto, sem consultar a identidade de quem deixou a pista. O contato sugerido não garante reconhecimento: é um encaminhamento de investigação, não uma resposta onisciente.

## Assembleia e confronto legado

`proof_strength` da assembleia usa o mesmo dossiê, em vez de contar IDs anexados. Dossiê aprovado tem força alta; um dossiê incompleto com exclusivo examinado tem força intermediária; comuns/singulares não examinados como pessoais têm força baixa. Argumento e relações ainda podem influenciar o voto social, sem transformar spam de objetos comuns em prova judicial.

O confronto legado usa a nova pontuação material para a pressão. A dificuldade continua variando por personagem e a confissão natural válida não é anulada por essa pontuação.

## Validação desta frente

Os testes de `test_evidence_specificity_v3.py` cobrem todos os sete culpados: primeiro dia rejeitado, segunda manhã solucionável com um civil morto, exame necessário e idempotente, distinção entre fontes, contradição pública alternativa, irrelevância dos campos privados, teto de comuns, variantes de peças e seleção por pilha.

A fixture compartilhada de um caso completo (quatro crimes) agora usa o exame canônico dos objetos que recolheu. Ela continua isolando os testes antigos de confissão, assembleia e jornal. O integrador executará a comparação de 100 cenários antes/depois; estes testes de regras não provam equilíbrio de jogadores humanos nem qualidade das falas livres.
