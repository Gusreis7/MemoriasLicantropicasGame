# Delegacia, transformação e população — revisão visual

Implementação em `feat/delegacia_feral_sociedade`, integrada em `develop` após validação.

## Lobisomem e delegacia

O lobisomem tem pelagem contínua, focinho longo, garras, pernas digitígradas e postura curvada. Não usa roupas ou acessórios. As quatro poses compartilham a mesma base dos pés no atlas, sem recorte ou edição dos pixels gerados.

A delegacia mostra mesa, cadeira, tinteiro, livros, lampião e chaves à esquerda; uma cela central; bancos, banquinhos, cabide e arquivo à direita. O cenário é estático. As grades são objetos separados na frente da pessoa detida e abrem para a soltura. Pés humanos e da fera usam a mesma linha do piso interno da cela; na saída, a pessoa caminha primeiro para o corredor frontal.

Cada transformação parte do sprite do personagem detido, incluindo suas roupas e aparência próprias. Homens e mulheres podem assumir o papel e transformar-se na mesma fera. Não há roupa masculina residual nem variantes de criatura que identifiquem antecipadamente o papel. O servidor continua confirmando transformação, soltura e vitória.

## Referências masculinas e femininas

`CharacterProfile.grammatical_gender` registra explicitamente a concordância do elenco: Capitu, Virgília e Florença usam `feminine`; Bentinho, Escobar, Rubião e Bacamarte, `masculine`. A projeção pública de personagem e o contexto autorizado do harness recebem esse dado de identidade, independente do papel sorteado.

Os textos que têm uma pessoa como sujeito usam a concordância correspondente: acusada/acusado, encontrada/encontrado, solta/solto e expulsa/expulso. A palavra portuguesa “lobisomem” mantém seu gênero gramatical; isso não determina o gênero da pessoa. Clientes sem o campo novo recebem frases neutras no frontend. Não é necessário reiniciar partidas ou sortear papéis novamente.

O painel administrativo recebe a mesma referência de gênero da ficha e usa viva/vivo, falecida/falecido e expulsa/expulso nos cartões. A galeria de suspeitos compartilha a função de concordância com o painel. O resultado da assembleia usa a formulação “Expulsão de [nome] confirmada”.

## Moradores

O atlas de população tem seis perfis e quatro poses de caminhada por perfil: quitandeira, estivador, costureira, jornaleiro adulto, caixeiro e cocheiro. Há quinze moradores nomeados distribuídos pelos cinco locais, três em cada um. Nome e ofício aparecem ao passar o ponteiro; a descrição acessível da cena também os identifica. Os pés ficam na linha do chão, a caminhada respeita movimento reduzido e os sprites são preservados durante atualizações do mundo.

Esses moradores ampliam a população visual. Os sete suspeitos continuam sendo os agentes de investigação, com conversas e depoimentos regidos pelo servidor; os figurantes não são fontes de evidências ou participantes do sorteio.

| Local | Moradores |
| --- | --- |
| Praça Verde | Rita, quitandeira; Joaquim, jornaleiro; Antônio, cocheiro |
| Cabana da Capitu | Elisa, costureira; Rosária, quitandeira; Manoel, cocheiro |
| Casa Verde | Amélia, costureira; Augusto, caixeiro; Júlio, jornaleiro |
| Café do Largo | Alberto, caixeiro; Leonor, costureira; Sebastião, cocheiro |
| Cais das Lanternas | Pedro, estivador; Benedita, quitandeira; Vicente, jornaleiro |

Os nomes, roupas, distribuição e delegacia são composições ficcionais. A referência social é o Rio de 1890, já usado pelo jogo, com trabalhadores do porto, comércio de rua e diferentes meios sociais. Foram consultados a [MultiRio sobre quiosques e trabalhadores urbanos](https://multi.rio/index.php/historia-do-brasil/rio-de-janeiro/2915-os-quiosques-e-os-corticos-do-rio-republicano), a [Biblioteca Nacional sobre quitandeiras, pequenos lavradores, comércio e tipógrafos no século XIX](https://bndigital.bn.gov.br/artigos/mercado-em-greve-protestos-e-organizacao-dos-trabalhadores-do-pequeno-comercio-no-rio-de-janeiro-outubro-1885/) e a [pesquisa da UFF sobre cocheiros e carroceiros entre 1870 e 1906](https://www.historia.uff.br/stricto/td/1404.pdf). As escolhas de desenho não pretendem reconstruir uniformes ou uma delegacia histórica específica.

## Assets e proveniência

Produzidos com **image_gen built-in**, preservando resolução e transparência originais:

- `frontend/public/assets/cinematics/werewolf.png` e `werewolf.json` — substituição solicitada da fera vestida.
- `frontend/public/assets/cinematics/jail.png` — ampliação solicitada da delegacia.
- `frontend/public/assets/ambient/citizens.png` e `citizens.json` — novo atlas de moradores, 24 frames.

Os prompts completos, referências e arquivos de origem estão em [feral-police-prompts.json](../frontend/public/assets/cinematics/feral-police-prompts.json). O registro anterior de prompts descreve a versão original; este arquivo registra a substituição desta revisão.

## Validação

- 543 testes Python aprovados contra Redis real em namespace isolado, incluindo transformação e soltura para cada um dos sete personagens.
- 42 testes frontend aprovados e build TypeScript/Vite concluído.
- 14 fluxos E2E no Brave aprovados, cobrindo os cinco locais, transformação masculina e feminina, soltura e navegação. Após a revisão final de concordância, os três fluxos afetados (admin, delegado e assembleia) foram repetidos com sucesso; 41 testes Python dos módulos afetados também foram revalidados.
- Inspeção das capturas da delegacia com Florença, Bentinho transformado e do cais com os novos moradores: pés no piso, criatura sem roupas, transparência preservada e mobiliário nos três setores.

Build Docker atualizado e conferido no Brave: jogo na porta7077 e admin na7078, com login, consulta de estado e logout aprovados.

Os testes não fazem chamadas reais a modelos. O estado persistido das partidas e o volume Redis de desenvolvimento são preservados.
