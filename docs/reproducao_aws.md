# Publicação com Elastic IP, Registro.br e Caddy

Leia a [arquitetura AWS](solucao_aws.md). O fluxo é: preparar a base → provisionar EC2/EIP → cadastrar registro A → publicar → verificar HTTPS. Não há etapa de delegação Route53 ou validação ACM.

## 1. Preparar e atualizar a base

Use AWS CLI v2, Terraform (CI usa 1.17.1, mínimo 1.11.4), Python 3.13/uv, GitHub CLI e Session Manager Plugin. O assistente fixa perfil `terraform`, região `us-east-1` e o repositório autorizado. Na raiz:

```sh
uv sync --locked
aws sts get-caller-identity --profile terraform --region us-east-1
gh auth status
uv run python scripts/bootstrap_aws.py plan --account-id 681835981654
terraform -chdir=infra/terraform/bootstrap show ../../../artifacts/aws-bootstrap/reviewed.tfplan
```

Confira que o plano preserva o EBS, buckets/state, rede e recursos legados. A mudança esperada para a base já existente é adicionar um EIP e atualizar IAM/outputs; não substituir o volume ou a VPC. Depois de revisar:

```sh
uv run python scripts/bootstrap_aws.py apply --account-id 681835981654
uv run python scripts/bootstrap_aws.py configure --account-id 681835981654
```

A primeira criação de uma base usa state local e migração para S3; execuções posteriores reutilizam o state existente. O assistente recusa states divergentes, plano alterado ou remoções/substituições. Preserve arquivos de state, backups e metadados de backend. Os planos ficam em `artifacts/aws-bootstrap/`, ignorado pelo Git.

O provider OIDC existente é reutilizado. O prefixo efetivo é consultado no GitHub; não é adivinhado. Configure cadastra as cinco variáveis dos workflows e os ambientes restritos a main sem remover proteções existentes. A senha é lida por getpass e enviada diretamente ao Parameter Store, sem argumentos de processo ou arquivos; uma senha já cadastrada é preservada.

## 2. Provisionar EC2 e associar o EIP

Publique a implementação revisada em main antes de usar os workflows. Inicie o plano:

```sh
gh workflow run infrastructure.yml --repo Gusreis7/MemoriasLicantropicasGame --ref main -f operation=plan
gh run list --repo Gusreis7/MemoriasLicantropicasGame --workflow infrastructure.yml --limit 5
```

Confira os logs e execute apply, aguardando sucesso:

```sh
gh workflow run infrastructure.yml --repo Gusreis7/MemoriasLicantropicasGame --ref main -f operation=apply
```

O workflow imprime `public_ip`. O EIP é dedicado ao jogo, permanece alocado na base e não pode ser reassociado silenciosamente de outra instância.

Como alternativa local, após o bootstrap aplicado, use os mesmos states S3 e um plano salvo:

```sh
export AWS_PROFILE=terraform AWS_REGION=us-east-1
terraform -chdir=infra/terraform/app init -lockfile=readonly -backend-config=bucket=memorias-licantropicas-681835981654-tfstate -backend-config=key=production/terraform.tfstate -backend-config=region=us-east-1 -backend-config=encrypt=true -backend-config=use_lockfile=true
terraform -chdir=infra/terraform/app plan -var=state_bucket=memorias-licantropicas-681835981654-tfstate -out=reviewed.tfplan
terraform -chdir=infra/terraform/app show -json reviewed.tfplan | python3 scripts/check_infrastructure_plan.py apply
terraform -chdir=infra/terraform/app show reviewed.tfplan
# Após revisar o plano:
terraform -chdir=infra/terraform/app apply reviewed.tfplan
terraform -chdir=infra/terraform/app output -raw public_ip
```

Não execute o fluxo local e os workflows em paralelo. O lock do state protege cada raiz; a atualização da base deve terminar antes do plano de app. Cloud-init prepara o host e o disco, mas não baixa a aplicação antes da entrega.

## 3. Cadastrar o registro A no Registro.br

Na zona DNS que é autoritativa para `gustavodreis.dev.br`, cadastre:

| Campo | Valor |
| --- | --- |
| Tipo | A |
| Nome | `memoriaslicantropicasgame` |
| Destino | `98.95.157.47`, EIP provisionado nesta implantação |

Se a interface pedir o nome completo, use `memoriaslicantropicasgame.gustavodreis.dev.br`. Não use o IP público temporário da EC2. Remova A/AAAA conflitantes desse hostname. Não é necessário mudar os nameservers de todo o domínio.

Alocação confirmada na AWS: `eipalloc-0802363bb84135383`. Para futuras recriações, confira novamente `terraform output -raw public_ip`; esse output é a referência operacional.

Nesta implantação a associação foi confirmada com a EC2 `i-00079ff6f9b0e7b08`, SSM Online e security group expondo somente 80/443 TCP. O volume `vol-07cb5703329d861d8` foi preservado. A base aplicou 1 criação/2 atualizações e a aplicação 8 criações, sem destruições. A emissão do certificado e a verificação externa de HTTPS aguardam o registro A e o delivery do código novo; ainda não são resultados confirmados.

O diagnóstico remoto via SSM também confirmou cloud-init concluído, Docker ativo, EBS montado em `/srv/ml-data` com ext4 e diretórios de dados/configuração do Caddy existentes, privados e pertencentes a UID/GID 1000. Os testes locais incluem validação do Caddyfile na imagem oficial fixada, 26 testes Python de bootstrap/deploy e os dois testes Terraform com provider simulado.

Se o subdomínio já estiver delegado por NS à zona Route53, o registro A no pai será ignorado enquanto a delegação existir. Revise essa delegação no provedor de DNS, mantendo a zona AWS preservada até decidir sua limpeza. Se o DNS autoritativo do domínio pai não for o Registro.br, edite o registro no provedor autoritativo efetivo.

Confira a propagação:

```sh
dig +short A memoriaslicantropicasgame.gustavodreis.dev.br
dig +short AAAA memoriaslicantropicasgame.gustavodreis.dev.br
```

O A deve retornar somente o EIP do jogo; não deve haver AAAA sem IPv6 funcional. A emissão pública depende desse apontamento e do acesso externo às portas 80/443.

## 4. Publicar e verificar HTTPS

Após o DNS apontar corretamente:

```sh
gh workflow run delivery.yml --repo Gusreis7/MemoriasLicantropicasGame --ref main
gh run list --repo Gusreis7/MemoriasLicantropicasGame --workflow delivery.yml --limit 5
curl --fail https://memoriaslicantropicasgame.gustavodreis.dev.br/health
curl -I http://memoriaslicantropicasgame.gustavodreis.dev.br
```

O delivery preserva ECR por digest → manifesto S3 → instalação SSM. Caddy inicia junto da aplicação e solicita o certificado. HTTPS deve ter certificado confiável e HTTP deve redirecionar para HTTPS. O workflow aguarda DNS/HTTPS; não depende de ALB. Não use curl -k para considerar emissão bem-sucedida.

O scan ECR também é assíncrono: o delivery consulta `describe-image-scan-findings`, aguarda indexação/processamento por até cinco minutos e diferencia falha de permissão, status não suportado e vulnerabilidades encontradas. HIGH/CRITICAL continuam bloqueando a instalação e são exibidas com CVE/pacote/versão. A API usa Python 3.13 Alpine/musl e a interface usa Nginx 1.30.6 Alpine, ambos fixados por digest, com atualização dos pacotes de sistema durante o build. `uv.lock` e `package-lock.json` permanecem separados dessas atualizações. Um build bem-sucedido não substitui o scan real do ECR.

Na auditoria da role `memorias-licantropicas-delivery`, a política efetiva e a simulação IAM confirmaram leitura do scan ECR, escrita do manifesto no caminho previsto e envio do documento SSM à instância com a tag Project. A confiança OIDC está limitada ao subject imutável do repositório e ao ambiente production, sem permissions boundary. Não foi necessário ampliar a política para corrigir a espera pelo scan. As simulações são verificações de política, não uma execução completa de entrega autenticada por OIDC.

A revisão das imagens substituiu Debian/glibc por Alpine/musl na API, atualizou o Nginx para 1.30.6 e zlib para 1.4 via atualizações do Alpine. O pip de sistema e seus pacotes vendorizados foram removidos: a imagem usa uv e não precisa deles. O build evita cache de instalação. Os locks Python e npm foram preservados. Trivy local, com base de vulnerabilidades atualizada, retornou zero HIGH/CRITICAL na API e no frontend; relatórios em `artifacts/security/api-alpine-trivy.json` e `web-alpine-trivy.json`, fora do Git. Essa evidência é do scan local e não substitui o novo resultado do ECR no Actions. A role também foi confirmada como impedida de publicar em repositório ECR de outro projeto ou enviar `AWS-RunShellScript`.

Em caso de falha, com uma sessão operacional autorizada na EC2, consulte:

```sh
sudo systemctl status ml-game.service
sudo journalctl -u cloud-final -u ml-game --no-pager -n 100
sudo docker compose --env-file /run/ml-game/images.env -f /etc/ml-game/compose.yaml logs --tail=100 caddy game
```

Confira erros ACME, A/AAAA, firewall, portas e persistência de `/srv/ml-data/caddy`. Não apague certificados ou repita emissões em ciclos rápidos. Uma instalação saudável internamente pode ter HTTPS ainda pendente; corrija o DNS e confira novamente.

Teste também uma partida e uma tarefa de inferência: o endpoint de saúde não comprova acesso ao modelo.

## 5. Admin e preservação

O admin continua somente no loopback da EC2. Com uma identidade operacional autorizada:

```sh
aws ssm start-session --profile SEU_PERFIL_OPERADOR --region us-east-1 --target i-INSTANCE_ID --document-name memorias-licantropicas-admin-tunnel --parameters 'localPortNumber=["7078"]'
```

Abra http://127.0.0.1:7078 e faça login. O painel não passa pelo Caddy público.

A zona Route53, o CNAME de validação e o certificado ACM antigos continuam no bootstrap. Sua remoção não faz parte deste deploy. Uma proposta de limpeza deve listar IDs, dependências e plano separado, preservando a zona pai e o DNS de outros serviços. ALB/alias presentes em um state app antigo também exigem revisão separada: o workflow bloqueia sua destruição no apply comum.

Destruir app preserva EIP, EBS, certificados Caddy no EBS, state e rede. A EC2 pode ser recriada na mesma AZ e associada ao mesmo EIP. Essa base continua gerando custos enquanto existir.

Referência: [HTTPS automático do Caddy](https://caddyserver.com/docs/automatic-https).
