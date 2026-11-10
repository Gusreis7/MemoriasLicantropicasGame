# Reprodução na AWS

Publiquei esta versão para experimentar a aplicação completa, da infraestrutura
até as conversas entre os personagens. Durante o desenvolvimento usei **créditos
da AWS** e o **Qwen3-32B (`qwen.qwen3-32b`)** como LLM principal, acessado pelo
**Amazon Bedrock Mantle** em `us-east-1`.

Este guia reproduz a publicação com **sua própria conta, repositório e domínio**.
Os créditos utilizados no projeto não são transferidos para outras instalações:
EC2, EBS, rede e chamadas ao modelo podem gerar cobranças. Ainda não há suporte
pronto a LLMs locais; a reprodução exige acesso ao Bedrock para os diálogos.
Se quiser apenas experimentar na sua máquina, sem provisionar uma EC2, siga o
[guia local](deploy_local.md). A inferência, nesse caso, continua na AWS.

## O que a infraestrutura resolve

Separei a base permanente da instância que executa a aplicação. Assim, posso
publicar uma nova versão por GitHub Actions sem reconfigurar o servidor
manualmente e sem vincular as partidas ao ciclo de vida da EC2.
O desenho está em [arquitetura AWS](solucao_aws.md).

| Objetivo | Como foi organizado |
| --- | --- |
| Ter uma base de rede própria | VPC, duas subnets públicas em zonas distintas e rotas criadas pelo Terraform |
| Manter um endereço público estável | Elastic IP reservado para a EC2, com registro A no seu provedor DNS |
| Automatizar HTTPS | Caddy emite e renova o certificado no servidor |
| Preservar partidas e certificados | Redis e dados do Caddy ficam no EBS, na mesma zona da instância |
| Restringir o acesso administrativo | Admin em loopback, acessível por túnel SSM e login; sem SSH público |
| Saber qual versão está instalada | Imagens identificadas por digest no ECR e manifesto de release no S3 |
| Automatizar a entrega | GitHub Actions assume roles por OIDC e instala a versão por SSM |

Separei o Terraform em `bootstrap`, que mantém a base permanente, e `app`, que
mantém a EC2 e suas associações. Os states ficam no S3 com versionamento e lock.
A configuração atual usa uma única instância: as duas subnets não representam
redundância da aplicação. EBS persistente também não substitui backup.

## Requisitos e custos

Para reproduzir o ambiente, prepare:

- **Conta AWS e permissões:** uma identidade para criar e administrar a rede,
  buckets, ECR, IAM/OIDC, EC2, EBS, Elastic IP e documentos e parâmetros SSM.
  O perfil local usado pelo assistente se chama `terraform`. As roles dos
  workflows são criadas na preparação da base e têm funções separadas.
- **Acesso ao modelo:** a identidade de execução da aplicação precisa de
  permissão para invocar o Qwen3-32B no Bedrock Mantle. Provisionar a EC2 não
  habilita automaticamente o acesso ao modelo. Confira disponibilidade,
  permissões e eventuais limites antes de testar as conversas.
- **Repositório GitHub:** uma cópia em que você possa configurar Actions,
  variáveis e ambientes. Para publicar pelo seu próprio push, use um fork e
  adapte as restrições de repositório e domínio indicadas mais abaixo.
- **Domínio e DNS:** acesso à zona DNS autoritativa para cadastrar um registro A
  com o IP obtido no provisionamento. Se usar Registro.br, faça o apontamento
  nele; se o DNS estiver em outro provedor, faça a alteração nesse provedor.
- **Ferramentas locais:** Git, AWS CLI v2, Terraform, Python 3.13, `uv`, GitHub CLI
  e Session Manager Plugin. Use a versão de Terraform fixada no workflow para
  reproduzir a execução do CI.
- **Custos e capacidade:** confirme a disponibilidade em `us-east-1` da
  instância padrão `m7i-flex.large`, do EBS e do Elastic IP. Infraestrutura,
  armazenamento, tráfego e inferência podem ser cobrados mesmo em testes.
  Desligar a aplicação não remove os recursos permanentes nem interrompe
  necessariamente todos os custos.

Na primeira instalação, sigo a ordem **adaptar o fork → preparar a base →
criar a EC2 → apontar o DNS → publicar → validar HTTPS e uma conversa**.
Nas próximas versões, o push em `main` atualiza a aplicação; mudanças de
infraestrutura continuam exigindo plano e aplicação separados.

Os comandos abaixo operam a sua instalação. Se já houver recursos ou state do
projeto na conta, confira o inventário e o plano antes de aplicar qualquer mudança.

## 0. Preparar o repositório e a conta

Para publicar pela sua conta do GitHub, comece criando um
[fork deste repositório](https://github.com/Gusreis7/MemoriasLicantropicasGame/fork).
Clone a sua cópia e entre na pasta do projeto, substituindo os exemplos abaixo:

```sh
git clone https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
cd SEU_REPOSITORIO
```

Para apenas explorar o código ou rodar localmente, você pode clonar
[o repositório original](https://github.com/Gusreis7/MemoriasLicantropicasGame)
seguindo o [guia local](deploy_local.md). A publicação por push deve usar um
repositório em que você tenha permissão para configurar e executar os workflows.

Instale AWS CLI v2, Terraform compatível com os workflows, Python 3.13, `uv`,
GitHub CLI e Session Manager Plugin. O assistente usa a região `us-east-1` e
exige um perfil AWS chamado `terraform`. Configure esse perfil com as suas
credenciais e confirme a conta antes de continuar:

```sh
aws sts get-caller-identity --profile terraform --region us-east-1
gh auth status
uv sync --locked
```

Defina os valores da sua instalação no terminal. Troque os exemplos antes de executar:

```sh
export AWS_PROFILE=terraform
export AWS_REGION=us-east-1
export GH_REPO='SEU_USUARIO/SEU_REPOSITORIO'
export GAME_DOMAIN='jogo.seudominio.com.br'
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
```

**Se estiver usando um fork, adapte as restrições do código primeiro.** Hoje não
basta definir essas variáveis: o projeto ainda limita repositório e domínio nos
seguintes arquivos:

- `scripts/bootstrap_aws.py`: repositório, domínio usado no inventário e nas variáveis geradas.
- `scripts/deliver_aws.py`: repositório autorizado a publicar.
- `infra/terraform/bootstrap/variables.tf`: domínio e validação do subject OIDC.
- `.github/workflows/`: repositório autorizado e confirmação de destruição.

Ajuste também o exemplo de tfvars e os testes que conferem essas restrições. Mantenha
as restrições para o seu repositório e domínio, sem liberar curingas. As variáveis
acima organizam os comandos deste guia; não substituem essas configurações.

## 1. Preparar a base

```sh
uv run python scripts/bootstrap_aws.py plan --account-id "$AWS_ACCOUNT_ID"
terraform -chdir=infra/terraform/bootstrap show ../../../artifacts/aws-bootstrap/reviewed.tfplan
```

Confira o plano. Se ele corresponde ao que você quer criar ou atualizar:

```sh
uv run python scripts/bootstrap_aws.py apply --account-id "$AWS_ACCOUNT_ID"
uv run python scripts/bootstrap_aws.py configure --account-id "$AWS_ACCOUNT_ID"
```

O assistente verifica recursos e states existentes. Na primeira execução, cria a
base e migra o state para S3; nas seguintes, reutiliza esse state. Não apague state,
backups ou arquivos de backend para tentar resolver uma falha.

Você não precisa copiar o tfvars de exemplo ao usar o assistente: ele gera suas
variáveis em `artifacts/aws-bootstrap/`. Essa pasta fica fora do Git.

A etapa `configure` reutiliza o provider OIDC quando ele já existe, confere o
subject do repositório e cadastra as variáveis no GitHub em **Settings → Secrets
and variables → Actions → Variables**:

| Variável | De onde vem |
| --- | --- |
| `AWS_ACCOUNT_ID` | Identidade AWS confirmada |
| `AWS_REGION` | Região da instalação |
| `TF_STATE_BUCKET` | Output `state_bucket` do bootstrap |
| `AWS_INFRASTRUCTURE_ROLE_ARN` | Output da role de infraestrutura |
| `AWS_DELIVERY_ROLE_ARN` | Output da role de entrega |

Esses valores também aparecem nos outputs do state; o GitHub não lê o state para
preencher suas variáveis automaticamente. A etapa `configure` faz essa ligação.
Ela também prepara os ambientes dos workflows e pede a senha administrativa sem
mostrá-la. A senha vai para o Parameter Store como `SecureString`, não para o
GitHub nem para o state. Uma senha já cadastrada é preservada.

## 2. Criar a EC2 e obter o IP

Envie a configuração revisada para `main`. Depois, gere o plano pelo GitHub:

```sh
gh workflow run infrastructure.yml --repo "$GH_REPO" --ref main -f operation=plan
gh run list --repo "$GH_REPO" --workflow infrastructure.yml --limit 5
```

Leia o resultado antes de aplicar:

```sh
gh workflow run infrastructure.yml --repo "$GH_REPO" --ref main -f operation=apply
```

Ao terminar, o workflow mostra `public_ip`. Esse é o Elastic IP da sua instalação.
Consulte também o ID da instância na EC2 ou no output `instance_id` para o túnel
administrativo. Se usar Terraform localmente, inicialize a raiz `app` com o bucket indicado por
`TF_STATE_BUCKET`, chave `production/terraform.tfstate` e lock S3; não crie um
state local paralelo. Use um único fluxo de aplicação por vez.

## 3. Apontar o DNS

No provedor autoritativo do seu domínio, como o Registro.br, crie:

| Campo | Valor da sua instalação |
| --- | --- |
| Tipo | A |
| Nome | Subdomínio escolhido, como `jogo` |
| Destino | Elastic IP mostrado pelo Terraform |

Use o IP reservado, não um endereço temporário da EC2. Confira registros A/AAAA
conflitantes e eventuais delegações NS antigas do subdomínio. O fluxo atual não
precisa de delegação Route53 nem de validação ACM.

```sh
dig +short A "$GAME_DOMAIN"
dig +short AAAA "$GAME_DOMAIN"
```

O A deve retornar o seu Elastic IP. Só mantenha AAAA se houver IPv6 funcional.

## 4. Publicar a aplicação

Com a base configurada e o DNS correto, um push em `main` dispara a entrega.
Você também pode iniciá-la manualmente:

```sh
gh workflow run delivery.yml --repo "$GH_REPO" --ref main
gh run list --repo "$GH_REPO" --workflow delivery.yml --limit 5
curl --fail "https://$GAME_DOMAIN/health"
curl -I "http://$GAME_DOMAIN"
```

O Actions constrói e verifica as imagens, publica no ECR por digest, grava o
manifesto no S3 e instala por SSM. Caddy emite o certificado e renova-o
automaticamente. HTTP deve redirecionar para HTTPS, com certificado válido.

Se a entrega falhar depois da instalação, confira DNS, portas 80/443 e logs do
Caddy. No host, por uma sessão SSM autorizada:

```sh
sudo systemctl status ml-game.service
sudo journalctl -u cloud-final -u ml-game --no-pager -n 100
sudo docker compose --env-file /run/ml-game/images.env -f /etc/ml-game/compose.yaml logs --tail=100 caddy game
```

Erros de resolução podem vir também do DNS de saída do host ou do Docker.
Não apague certificados para corrigir DNS. Se o bloqueio vier do scan ECR, leia
as vulnerabilidades ou o erro de permissão antes de tentar novamente.
Por fim, abra o jogo, inicie uma investigação e converse com um NPC. O
`/health` comprova apenas que API e Redis estão disponíveis; não confirma a
permissão de invocar Qwen3-32B nem a qualidade da geração. Consulte o uso no
painel administrativo e a cobrança efetiva na sua conta AWS.

## 5. Admin e preservação

O admin fica no loopback da EC2. Use seu perfil operacional e o ID da sua instância:

```sh
export OPERATOR_PROFILE='SEU_PERFIL_OPERADOR'
export INSTANCE_ID='ID_DA_SUA_INSTANCIA'
aws ssm start-session \
  --profile "$OPERATOR_PROFILE" \
  --region "$AWS_REGION" \
  --target "$INSTANCE_ID" \
  --document-name memorias-licantropicas-admin-tunnel \
  --parameters 'localPortNumber=["7078"]'
```

Deixe o terminal aberto e acesse http://127.0.0.1:7078. O túnel não dispensa o
login. Outra porta local exige ajustar `ADMIN_ALLOWED_ORIGINS` e publicar a
configuração da API. O painel é somente de leitura.

Para trocar a senha de produção:

```sh
uv run python scripts/configure_aws_admin.py --profile "$AWS_PROFILE" --region "$AWS_REGION" --overwrite
```

O script pede e confirma uma senha com pelo menos 24 caracteres. Depois, faça um
novo deploy para a API carregar o valor atualizado. A senha local continua no
`.env` e é independente da senha de produção.

O EBS guarda Redis e certificados do Caddy; o bootstrap mantém disco,
Elastic IP, rede e state mesmo quando a aplicação é removida. Esses recursos
continuam gerando custos, independentemente de ter créditos promocionais.
Recursos antigos de ACM, Route53 ou ALB exigem um plano de limpeza separado;
não os remova como parte de uma publicação comum.
