# Reprodução na AWS

A infraestrutura tem duas raízes: `bootstrap` mantém rede, EBS, DNS, ECR, buckets e identidades; `app` mantém EC2, ALB e acesso público. A [arquitetura](solucao_aws.md) detalha os serviços.

## Pré-requisitos

Execute os comandos na raiz do checkout. Instale AWS CLI v2, Terraform (CI usa 1.17.1; configuração exige >=1.11.4), GitHub CLI, Python 3.13 e uv. Para acesso administrativo, instale também o Session Manager Plugin.

Autentique o perfil AWS `terraform` e o GitHub CLI com permissão administrativa no repositório `Gusreis7/MemoriasLicantropicasGame`. A região do assistente é fixa: `us-east-1`.

```sh
uv sync --locked
aws sts get-caller-identity --profile terraform --region us-east-1
gh auth status
uv run python scripts/bootstrap_aws.py --help
```

O domínio permanece `memoriaslicantropicasgame.gustavodreis.dev.br`. Você precisa controlar o DNS pai `gustavodreis.dev.br`. A EC2 continua `m7i-flex.large`, com Redis em EBS gp3 criptografado persistente de 20 GiB por padrão.

## 1. Inspecionar e planejar a fundação

Na inspeção realizada nesta entrega, a identidade do perfil foi confirmada como `arn:aws:iam::681835981654:user/terraform`. O provider OIDC existente e o prefixo efetivo `repo:Gusreis7@89582195/MemoriasLicantropicasGame@1437666201` foram confirmados por consultas reais. O bucket esperado retornou 404; as consultas de tag do projeto, VPC, EBS, ECR e zona DNS não retornaram recursos correspondentes. Isso não substitui a inspeção de IAM: as três consultas `iam:GetRole` foram negadas para `memorias-licantropicas-runtime`, `memorias-licantropicas-infrastructure` e `memorias-licantropicas-delivery`.

Por esse motivo, o comando `plan` foi interrompido antes de executar Terraform. Nenhum plano real foi aplicado, nenhum NS foi emitido e nenhum workflow de deploy foi disparado nesta entrega. Um administrador da conta deve revisar as permissões do perfil `terraform`, começando por `iam:GetRole` nos ARNs `arn:aws:iam::681835981654:role/memorias-licantropicas-{runtime,infrastructure,delivery}` (a expressão entre chaves representa três ARNs, não sintaxe de política IAM). O perfil também precisa das permissões de criação/leitura/atualização dos recursos da fundação. Corrigir apenas a primeira negação não comprova que todas as demais permissões estejam disponíveis. Não amplie as roles de CI para contornar essa falta de acesso do operador.

Localmente, foram validados os planos com provider simulado nas duas raízes Terraform, o assistente com AWS/GitHub simulados e a configuração de isolamento dos containers. Publicação no ECR, execução do SSM, boot da EC2 e conectividade do modelo dependem da conclusão do deploy real abaixo.

```sh
uv run python scripts/bootstrap_aws.py plan --account-id 681835981654
terraform -chdir=infra/terraform/bootstrap show ../../../artifacts/aws-bootstrap/reviewed.tfplan
```

O assistente confere identidade AWS, states local e S3, inventário por tags e nomes fixos, zona DNS, repositórios ECR e provider OIDC. Erros de permissão não são interpretados como ausência. Recursos existentes sem state gerenciável ou states divergentes interrompem o fluxo; recupere/importe o state antes de prosseguir.

O subject OIDC vem da API do GitHub, inclusive o formato imutável com IDs. Não é deduzido pela data de criação do repo. `--oidc-subject-prefix` é um recurso para conferência manual quando a API não informa o formato; não substitui a consulta dos IDs ou permite outro repositório.

A primeira execução usa state local para criar o próprio bucket. Nas seguintes, o assistente inicializa o backend S3 existente. Ele salva o plano revisável e metadados em `artifacts/aws-bootstrap/`, fora do Git. Esse diretório pode conter state de planejamento e informações da conta; preserve suas permissões privadas.

A rede é criada pelo Terraform: VPC `10.42.0.0/16`, DNS habilitado, Internet Gateway, subnets públicas `10.42.0.0/24` e `10.42.1.0/24`, tabela de rotas com saída `0.0.0.0/0` e duas associações. AZs padrão: `us-east-1a` e `us-east-1b`. A subnet primária e o EBS usam a mesma `availability_zone`. Não informe `vpc_id` ou `public_subnet_ids`.

Para mudar CIDR/AZ antes da primeira criação, use um `terraform.tfvars` local na raiz bootstrap, conforme o exemplo. Se já houver EBS, preserve sua AZ. Em uma base antiga, aplicar o novo bootstrap muda os outputs da rede; planeje depois a aplicação e revise a substituição da EC2/ALB. O disco persistente não deve ser substituído.

## 2. Aplicar o plano revisado

Após revisar o plano:

```sh
uv run python scripts/bootstrap_aws.py apply --account-id 681835981654
```

Essa etapa cria recursos cobrados. Antes de aplicar, o assistente verifica novamente identidade, OIDC, state, fonte e integridade do plano. Não aplica remoções/substituições automaticamente.

Após a primeira criação, migra o state local para `bootstrap/terraform.tfstate` no bucket `memorias-licantropicas-681835981654-tfstate`, com criptografia, versionamento e `use_lockfile=true`. O backend gerado fica em `backend.tf` ignorado pelo Git. Não apague states, metadados de backend ou backups para resolver um erro; se a aplicação/migração for interrompida, preserve os arquivos e recupere a operação antes de repetir.

## 3. Delegar o DNS

O comando apply imprime os **NS reais** da zona criada. Você também pode recuperá-los:

```sh
AWS_PROFILE=terraform AWS_REGION=us-east-1 terraform -chdir=infra/terraform/bootstrap output -json dns_nameservers
```

No provedor de DNS do domínio pai, crie a delegação NS para `memoriaslicantropicasgame` com todos os servidores retornados, exatamente como foram emitidos. Essa ação é externa ao Terraform do jogo. Não use servidores exemplificativos: os valores só existem depois do provisionamento.

Aguarde a propagação e a validação DNS do certificado ACM antes do apply da aplicação. O bootstrap cria o CNAME de validação dentro da zona delegada; a raiz app aguarda a emissão do certificado.

## 4. Configurar GitHub e senha administrativa

```sh
uv run python scripts/bootstrap_aws.py configure --account-id 681835981654
```

O assistente usa os outputs reais para cadastrar estas variáveis GitHub:

| Variável | Origem |
| --- | --- |
| `AWS_ACCOUNT_ID` | Identidade conferida |
| `AWS_REGION` | `us-east-1` |
| `TF_STATE_BUCKET` | Bucket do bootstrap |
| `AWS_INFRASTRUCTURE_ROLE_ARN` | Role de infraestrutura |
| `AWS_DELIVERY_ROLE_ARN` | Role de entrega |

Os ambientes `infrastructure`, `destruction` e `production` ficam restritos a `main`. Ambientes com proteções existentes incompatíveis exigem revisão manual em vez de remover reviewers ou regras silenciosamente. Configure aprovações adicionais no GitHub se desejar.

A senha administrativa é lida por `getpass`, confirmada e gravada diretamente pelo SDK AWS como `SecureString`, sem argumentos de processo, logs ou arquivos. Um parâmetro existente é preservado. Rotação é uma operação explícita:

```sh
uv run python scripts/configure_aws_admin.py --profile terraform --region us-east-1 --overwrite
```

A senha não entra em Terraform/state, manifesto S3 ou variáveis GitHub. Uma nova entrega recarrega a senha no arquivo temporário do host.

## 5. Provisionar aplicação e entregar

As alterações precisam estar publicadas em `main` para que os workflows executem o código correto. Depois do bootstrap, configuração e delegação DNS:

```sh
gh workflow run infrastructure.yml --repo Gusreis7/MemoriasLicantropicasGame --ref main -f operation=plan
gh run list --repo Gusreis7/MemoriasLicantropicasGame --workflow infrastructure.yml --limit 5
```

Confira o log do plano e, depois:

```sh
gh workflow run infrastructure.yml --repo Gusreis7/MemoriasLicantropicasGame --ref main -f operation=apply
```

Aguarde esse workflow terminar com sucesso antes de entregar:

```sh
gh workflow run delivery.yml --repo Gusreis7/MemoriasLicantropicasGame --ref main
gh run list --repo Gusreis7/MemoriasLicantropicasGame --workflow delivery.yml --limit 5
```

A entrega também dispara em push para main. Antes da infraestrutura/configuração inicial ela poderá falhar por pré-requisitos ausentes; repita manualmente depois das etapas acima.

O workflow constrói imagens linux/amd64, publica tags imutáveis com o commit, verifica vulnerabilidades, grava manifesto em `releases/COMMIT.json` e chama o documento SSM fixo. Na EC2, cloud-init prepara arquivos e EBS, o instalador confere commit/digests, inicia Compose e aguarda saúde. Nginx público recebe somente o ALB; admin continua em loopback por túnel SSM. A API usa a rede de saída explicitamente como gateway padrão. Não se abre SSH, Redis ou porta da API ao público.

```sh
curl --fail https://memoriaslicantropicasgame.gustavodreis.dev.br/health
```

Crie uma partida e teste uma tarefa com inferência; saúde HTTP não comprova acesso ao Bedrock. Examine também o painel e o resultado SSM. Restaurar imagens anteriores não restaura dados.

## 6. Admin privado e ciclo de vida

Use um perfil de operador autorizado com a política de túnel indicada pelo bootstrap. Substitua o ID da EC2 obtido no output da aplicação:

```sh
aws ssm start-session --profile SEU_PERFIL_OPERADOR --region us-east-1 --target i-INSTANCE_ID --document-name memorias-licantropicas-admin-tunnel --parameters 'localPortNumber=["7078"]'
```

Abra http://127.0.0.1:7078 e faça login. O túnel não elimina a autenticação do painel.

Destruir a raiz app pelo workflow exige a confirmação exata do domínio. A fundação continua, incluindo VPC, volume, zona, ECR e buckets, e pode continuar gerando custos. Remover definitivamente a fundação exige backup e decisão específica sobre as proteções `prevent_destroy`. Nunca remova o bucket que contém o state necessário para administrar os recursos.

O backend segue a [referência S3 do Terraform](https://docs.hashicorp.com/terraform/language/backend/s3), e o subject é conferido pela [API OIDC do GitHub](https://docs.github.com/en/rest/actions/oidc).
