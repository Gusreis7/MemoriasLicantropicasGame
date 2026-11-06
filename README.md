# Memórias Licantropicas

Um jogo de investigação na Rua do Ouvidor: Floriano interroga personagens de Machado de Assis, reúne provas e tenta identificar o lobisomem antes que a cidade sucumba.

São sete suspeitos por partida, com um lobisomem sorteado pelo servidor. NPCs têm relações, segredos e conhecimento próprio. Noites, álibis, fontes e consequências são determinados pelas regras; os modelos participam da expressão das personas e de escolhas narrativas limitadas.

## Começar localmente

Instale Git, Python 3, Make, Docker e Docker Compose. No checkout:

```sh
make setup
```

| Serviço | Endereço |
| --- | --- |
| Jogo | http://127.0.0.1:7077 |
| Painel administrativo | http://127.0.0.1:7078 |
| Documentação da API local | http://127.0.0.1:7079/docs |

O launcher prepara o `.env`, gera a senha administrativa e inicia os serviços. Consulte `ADMIN_USERNAME` e `ADMIN_PASSWORD` nesse arquivo para entrar no painel. Para inferência, configure um perfil AWS autorizado ou um bearer Bedrock no `.env`, conforme o [guia local](docs/deploy_local.md). O modelo padrão é `qwen.qwen3-32b` via Bedrock Mantle.

```sh
make status
make logs
make down
make up
```

`make down` preserva as partidas. `make setup` reconstrói a aplicação. `make destroy` apaga o Redis e todas as partidas.

## Tutorial: sua primeira investigação

1. Abra o jogo e inicie uma partida. Explore a rua e a cena do crime; examine e recolha os objetos disponíveis.
2. Aproxime-se de um personagem e converse como Floriano. Pergunte, por exemplo: “O que você fez ontem à noite?”.
3. Se o NPC disser que estava acompanhado, procure a outra pessoa e pergunte sobre a mesma noite. A confirmação recíproca transforma o relato em álibi confirmado. Um personagem sozinho não inventa companhia.
4. Pergunte sobre objetos, relações e acontecimentos. Distingua uma observação própria de uma fofoca repetida: várias pessoas reproduzindo a mesma fonte não são testemunhas independentes.
5. Consulte o caderno e os relatos destacados em roxo e dourado. Confira a noite, a fonte e o estado de confirmação antes de montar o caso.
6. Na delegacia, selecione as provas e os relatos pertinentes e apresente a acusação. A avaliação considera o conteúdo estruturado e a cobertura dos álibis.
7. Avance a investigação ou use o botão de pular o dia para chegar à manhã seguinte. O tempo traz novas consequências: quatro mortes do elenco atribuídas à fera encerram a partida em derrota. Brás Cubas, a vítima inicial, não entra nessa contagem.

O painel administrativo permite acompanhar sorteio, eventos, conversas e consumo de modelo para desenvolvimento e avaliação. Ele revela informações privadas da partida; seu acesso é separado do jogo.

## Como funciona

- **API:** Python 3.13, FastAPI e serviços de regras.
- **Estado:** Redis com persistência AOF; mesa, relações, memórias e rastros separados por partida.
- **Agentes:** ferramentas vinculadas à identidade de cada NPC, mestre da sessão e circulação social com LangGraph.
- **Modelos:** cliente Bedrock Mantle, saídas estruturadas e medição de uso. Fatos e permissões são definidos pelo servidor.
- **Interface:** TypeScript, Phaser e Vite; proxies Nginx no deploy.
- **Produção:** Terraform, EC2 com Elastic IP, registro A no Registro.br, HTTPS automático com Caddy, EBS, ECR, S3 e entrega por GitHub OIDC/SSM.

A investigação usa formato 2. Dados antigos incompatíveis são recusados; não há migração ou adaptador. O namespace Redis padrão `ml:v1` é independente desse formato.

## Desenvolvimento e validação

```sh
uv sync --locked
uv run pytest -q
cd frontend
npm ci
npm test
npm run build
```

A suíte comum não consome o modelo real. Os scripts `scripts/smoke_table_api.py` e `scripts/run_session_simulations.py` exercitam o servidor por HTTP; o segundo usa um LLM para interpretar Floriano e salva estatísticas por sessão. Veja os comandos, requisitos e limites em [testes e simulações](docs/testes.md).

## Documentação

| Guia | Objetivo |
| --- | --- |
| [Deploy local](docs/deploy_local.md) | Instalar, configurar, desenvolver e operar |
| [Solução AWS](docs/solucao_aws.md) | Entender a arquitetura e suas limitações |
| [Reprodução na AWS](docs/reproducao_aws.md) | Provisionar e entregar uma instalação |
| [Orquestração dos agentes](docs/orquestracao_agentes.md) | Entender NPCs, mestre, dados e permissões |
| [Índice técnico](docs/README.md) | Consultar mecânicas, interface e referências especializadas |

Recursos visuais e sonoros mantêm metadados, proveniência e atribuição junto aos arquivos. Documentos e relatórios antigos podem ser recuperados pelo histórico Git.


