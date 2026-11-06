# Reprodução na AWS

Este guia reproduz a solução versionada; ele não executa recursos na conta. Leia antes a [arquitetura AWS](solucao_aws.md). Os comandos de `apply` criam recursos cobrados e os de `destroy` removem recursos conforme o plano exibido.

## 1. Pré-requisitos e limites da configuração

Use AWS CLI v2, Session Manager Plugin, Terraform 1.17.1 (versão usada no CI), Git, Python e `uv`. Para entrega local via script, também são necessários Docker e Buildx. Use uma identidade AWS autorizada a criar a fundação e autentique seu perfil antes dos comandos.

A configuração está vinculada ao repositório `Gusreis7/MemoriasLicantropicasGame` e ao subdomínio `memoriaslicantropicasgame.gustavodreis.dev.br`. Para outro repositório/domínio, revise em conjunto as validações Terraform, subjects OIDC, políticas IAM, guards dos workflows, hosts permitidos e configuração de proxy. O guia abaixo assume os identificadores atuais.

Você precisa controlar o DNS pai `gustavodreis.dev.br`, ter uma VPC existente em `us-east-1`, pelo menos duas sub-redes públicas em zonas distintas e escolher a zona do volume/instância. As sub-redes precisam de saída pela internet e endereços disponíveis.

## 2. Criar a fundação

Na raiz do projeto:

```sh
export AWS_PROFILE=terraform
export AWS_REGION=us-east-1
aws sts get-caller-identity
cd infra/terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars
```

Edite `terraform.tfvars` com VPC, sub-redes, zona e subject OIDC reais. `create_github_oidc_provider = false` pressupõe que o provider GitHub já existe na conta; habilite sua criação somente se estiver ausente. O prefixo OIDC deve refletir o subject emitido pelo repositório: há formatos com IDs e formato legado, descritos no exemplo e validados em `variables.tf`. Não adivinhe os IDs.

```sh
terraform init
terraform fmt -check
terraform validate
terraform plan -out=bootstrap.tfplan
terraform apply bootstrap.tfplan
terraform output dns_nameservers
terraform output state_bucket
```

Delegue o subdomínio no DNS pai com os nameservers retornados. A emissão do certificado ACM depende dessa delegação; consulte também `foundation.validation_records` para diagnóstico. O plano do bootstrap e o estado local contêm dados operacionais da conta e devem ficar fora do Git.

## 3. Migrar o estado da fundação para S3

Copie `backend.s3.example` para `backend.s3.hcl` e substitua `ACCOUNT_ID` pelo ID da conta. Crie `backend.tf` com:

```hcl
terraform {
  backend "s3" {}
}
```

Migre o estado, mantendo uma cópia segura do estado local até confirmar a operação:

```sh
terraform init -migrate-state -backend-config=backend.s3.hcl
terraform state list
terraform output
```

Use a chave `bootstrap/terraform.tfstate`, criptografia e `use_lockfile = true`. Não use `-reconfigure` para substituir a migração inicial. Os arquivos locais de backend, `.tfvars`, estados e planos são ignorados pelo Git.

## 4. Cadastrar a senha administrativa

Volte à raiz do repositório e execute:

```sh
uv sync --locked
uv run python scripts/configure_aws_admin.py --profile terraform --region us-east-1
```

O script lê a senha sem eco e exige pelo menos 24 caracteres. Ela é salva como `SecureString` em `/memorias-licantropicas/production/admin-password`. Para rotação, use a opção explícita `--overwrite` e faça uma nova entrega para recarregar o arquivo no host. Não coloque a senha no Terraform, em commits ou em variáveis do workflow.

## 5. Configurar os ambientes do GitHub

Crie os ambientes `infrastructure`, `destruction` e `production`, restritos à branch `main`, com as proteções operacionais desejadas. Configure as variáveis do repositório:

| Variável | Origem |
| --- | --- |
| `AWS_ACCOUNT_ID` | ID da conta usada no bootstrap |
| `AWS_REGION` | `us-east-1` |
| `TF_STATE_BUCKET` | Output `state_bucket` |
| `AWS_INFRASTRUCTURE_ROLE_ARN` | Output `infrastructure_role_arn` |
| `AWS_DELIVERY_ROLE_ARN` | Output `delivery_role_arn` |

As roles confiam nos subjects OIDC dos ambientes configurados. Não adicione chaves AWS estáticas como alternativa. Confira os guards de repositório e branch nos dois workflows antes de executá-los.

## 6. Provisionar a aplicação

Execute o workflow **AWS infrastructure** (`infrastructure.yml`) primeiro com `operation=plan` e depois com `operation=apply`. O workflow inicializa o backend da raiz `app`, consulta a fundação e aplica o plano no mesmo job.

Para executar diretamente pelo Terraform, a partir da raiz do checkout, substitua `NOME_DO_BUCKET`:

```sh
cd infra/terraform/app
terraform init -backend-config='bucket=NOME_DO_BUCKET' -backend-config='key=production/terraform.tfstate' -backend-config='region=us-east-1' -backend-config='encrypt=true' -backend-config='use_lockfile=true'
terraform validate
terraform plan -var='state_bucket=NOME_DO_BUCKET' -out=app.tfplan
terraform apply app.tfplan
```

Não execute o fluxo local e o workflow ao mesmo tempo. Aguarde a inicialização da EC2 pelo cloud-init. O primeiro provisionamento prepara Docker, volume, firewall e arquivos de operação; o serviço só estará pronto para jogadores depois da entrega das imagens.

## 7. Entregar e conferir

Execute `delivery.yml` em `main`, ou integre uma mudança nessa branch para acionar o fluxo. A entrega exige exatamente uma instância em execução com as tags esperadas. O script constrói/publica as imagens, verifica o scan, grava o manifesto e espera o comando SSM terminar.

```sh
curl --fail https://memoriaslicantropicasgame.gustavodreis.dev.br/health
```

Abra o jogo, crie uma partida e converse com um NPC. A saúde HTTP não comprova acesso ao modelo; confirme também uma tarefa que use inferência e o consumo/falhas no admin. Não exponha a porta administrativa para facilitar essa verificação.

Se houver falha, confira o job de entrega e o resultado do comando SSM. Para manutenção com uma identidade operacional autorizada, consulte `cloud-init`, `ml-game.service`, Docker e `/srv/ml-data`; não altere o estado Terraform manualmente para esconder uma falha. A restauração de imagens pelo instalador não reverte dados.

## 8. Acessar o painel privado

Conceda ao operador a política indicada pelo output `admin_tunnel_policy_arn`. Com o Session Manager Plugin instalado, substitua perfil e instância:

```sh
aws ssm start-session --profile SEU_PERFIL_OPERADOR --region us-east-1 --target i-INSTANCE_ID --document-name memorias-licantropicas-admin-tunnel --parameters 'localPortNumber=["7078"]'
```

Abra http://127.0.0.1:7078 e use as credenciais administrativas configuradas. O documento dedicado permite o túnel para a porta prevista; as roles de CI não são perfis de manutenção interativa.

## 9. Parar, reconstruir ou remover

O workflow de infraestrutura com `operation=destroy` exige a confirmação exata `memoriaslicantropicasgame.gustavodreis.dev.br`. Ele remove a raiz `app`; a fundação continua, incluindo volume, DNS, certificado, imagens e estado. Esses recursos podem continuar cobrados.

Um novo `apply` seguido de entrega reutiliza o volume da fundação. Isso preserva também o formato dos dados: uma versão de código incompatível não recebe um banco limpo automaticamente. Planeje backup e limpeza explicitamente antes de uma troca incompatível. Não há adaptador para o formato antigo da investigação.

A remoção definitiva da fundação exige um procedimento separado, revisão das proteções `prevent_destroy`, backup e decisão explícita sobre dados e estado. Não destrua o bucket que ainda contém o estado necessário para administrar os demais recursos.
