# Memórias Licantópicas

Um jogo solo de investigação em que os outros participantes são personagens
controlados por agentes de IA.

Comecei este projeto pensando no  party game **Lobisomem**, uma das variações de Cidade
Dorme. Queria experimentar como seria investigar um caso em que, no lugar de
outros jogadores, eu pudesse conversar com personagens que guardam informações,
relações e segredos próprios. Aproveitei também a ambientação e algumas
referências à obra de Machado de Assis.

O resultado é uma investigação conduzida por Floriano , um detetive  que precisa descobrir
quem é a besta-fera antes que a cidade perca mais moradores. Os diálogos são
parte importante da experiência, mas não decidem sozinhos o que é verdade: a
mesa registra os acontecimentos, controla as provas e limita o que cada NPC
pode saber ou revelar.

## Como jogar

Você controla Floriano e investiga sete suspeitos. A ideia não é conseguir uma
confissão em uma única conversa, mas cruzar o que cada pessoa diz com os fatos
da partida.

1. Explore a cena do crime, examine o ambiente e recolha os objetos disponíveis.
2. Converse com os moradores sobre a noite anterior, suas relações e o que viram.
3. Confirme álibis com as pessoas citadas. Uma fofoca repetida não vira uma nova testemunha.
4. Consulte o caderno e os relatos destacados em roxo e dourado para organizar as pistas.
5. Vá à delegacia, selecione as evidências e apresente uma acusação quando achar que tem um caso.
6. Se ainda faltar informação, continue investigando ou avance para a manhã seguinte.

Use **A/D ou as setas** para andar e **E** para conversar ou examinar. Nas bordas
da rua, escolha o destino com as setas e confirme com **Enter**; **Esc** fecha
o menu. Também é possível viajar pelo mapa.

O jogo inclui um **Tutorial** no cabeçalho, aberto automaticamente na primeira
visita. Você pode consultá-lo de novo durante a partida. A investigação termina
em derrota se a fera causar a morte de quatro dos sete suspeitos; a vítima
inicial não entra nessa contagem.

## Modelo de IA e limitações atuais

Desenvolvi e experimentei o jogo utilizando **créditos da AWS**, com o
**Qwen3-32B (`qwen.qwen3-32b`)** como modelo principal, acessado pelo
**Amazon Bedrock Mantle** na região `us-east-1`.

**Por enquanto, não há opção pronta de usar LLMs locais**, como Ollama ou LM
Studio. Rodar o jogo no próprio computador significa executar a aplicação e
seus serviços localmente, **não** executar a inferência do modelo na máquina.
As conversas continuam dependendo de acesso ao Bedrock.

Os créditos usados no desenvolvimento não acompanham o repositório. Quem
reproduzir o projeto precisa de credenciais AWS próprias, permissão para usar
o modelo e deve considerar possíveis cobranças por inferência. Sem essas
credenciais, os serviços podem iniciar, mas a experiência de diálogo com os
personagens fica indisponível.

## Reproduzir na sua máquina

Com Git, Python 3, Make, Docker e Docker Compose instalados:

```sh
git clone https://github.com/Gusreis7/MemoriasLicantropicasGame.git
cd MemoriasLicantropicasGame
make setup
```

| Serviço | Endereço |
| --- | --- |
| Jogo | http://127.0.0.1:7077 |
| Painel administrativo | http://127.0.0.1:7078 |
| API e documentação | http://127.0.0.1:7079/docs |

O `make setup` prepara o `.env`, gera a senha administrativa, quando necessário,
e sobe os serviços. **Antes de iniciar uma partida completa**, configure no
`.env` um perfil AWS ou um token de acesso ao Bedrock e execute `make up`.
Os comandos, as opções de autenticação e a preservação das partidas estão no
[guia de reprodução local](docs/deploy_local.md).

Para publicar uma instância própria na AWS, consulte o
[guia de reprodução AWS](docs/reproducao_aws.md). Não é necessário provisionar
uma EC2 apenas para testar o jogo no computador.

## Como organizei o projeto

O backend é desenvolvido em **Python 3.13**, com **FastAPI**, **Redis**,
**LangGraph** e **LangChain Core**. O frontend utiliza **TypeScript**, **Phaser**
e **Vite**. A versão publicada na AWS usa **Terraform**, **EC2**, **EBS**,
**Caddy**, **GitHub Actions**, **ECR**, **S3** e **SSM**.

Separei as regras da investigação da geração de linguagem. A mesa determina
posições, noites, encontros, álibis e consequências; os agentes recebem apenas
as informações autorizadas para cada personagem. O servidor ainda valida as
respostas antes de registrá-las. Quando uma geração falha, existem respostas
determinísticas para os fluxos previstos pelas regras.

A explicação está em [NPCs e mestre da mesa](docs/orquestracao_agentes.md).

## Desenvolvimento

Desenvolvi o projeto em sessões de programação guiada com **Codex**, partindo
das mecânicas que queria testar. Usei especificações, planos de implementação,
revisão de diffs, testes e muitas partidas para identificar inconsistências.
Nem sempre um teste passando significava que a conversa ou a jogatina fazia
sentido; precisei revisar ambos.

Também utilizei geração de imagens para parte dos recursos visuais. Os sons
vieram de fontes externas e estão identificados nos
[créditos](docs/creditos_efeitos_open_source.md). Descrevi melhor o processo em
[uso de IA e Codex](docs/uso_ia_e_codex.md).

Para executar as verificações de desenvolvimento:

```sh
uv sync --locked
uv run pytest -q
cd frontend
npm ci
npm test
npm run build
```

Esses testes não chamam o modelo real. Os testes completos e as simulações com
inferência estão no [guia de testes](docs/testes.md).

## Documentação

- [Reprodução local](docs/deploy_local.md): instalação, Bedrock, dados e desenvolvimento.
- [Reprodução na AWS](docs/reproducao_aws.md): infraestrutura, domínio e publicação.
- [Arquitetura AWS](docs/solucao_aws.md): rede, serviços e persistência.
- [NPCs e mestre da mesa](docs/orquestracao_agentes.md): orquestração e limites dos agentes.
- [Testes](docs/testes.md): validações e simulações.
- [Uso de IA e Codex](docs/uso_ia_e_codex.md): processo de desenvolvimento.
- [Créditos dos efeitos](docs/creditos_efeitos_open_source.md): sons e licenças.
