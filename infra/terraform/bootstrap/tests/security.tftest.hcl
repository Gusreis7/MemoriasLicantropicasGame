mock_provider "aws" {
  override_during = plan
  mock_resource "aws_eip" {
    defaults = { id = "eipalloc-0123456789abcdef0", public_ip = "203.0.113.10", arn = "arn:aws:ec2:us-east-1:123456789012:elastic-ip/eipalloc-0123456789abcdef0" }
  }
  mock_resource "aws_vpc" { defaults = { id = "vpc-0123456789abcdef0", arn = "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-0123456789abcdef0" } }
  mock_resource "aws_subnet" { defaults = { id = "subnet-0123456789abcdef0", arn = "arn:aws:ec2:us-east-1:123456789012:subnet/subnet-0123456789abcdef0" } }
  mock_resource "aws_internet_gateway" { defaults = { id = "igw-0123456789abcdef0" } }
  mock_resource "aws_s3_bucket" { defaults = { id = "mock-bucket", arn = "arn:aws:s3:::mock-bucket" } }
  mock_resource "aws_ecr_repository" { defaults = { arn = "arn:aws:ecr:us-east-1:123456789012:repository/mock", repository_url = "mock-repository" } }
  mock_resource "aws_ebs_volume" { defaults = { id = "vol-0123456789abcdef0", arn = "arn:aws:ec2:us-east-1:123456789012:volume/vol-0123456789abcdef0" } }
  mock_resource "aws_route53_zone" { defaults = { id = "Z12345678", zone_id = "Z12345678", arn = "arn:aws:route53:::hostedzone/Z12345678" } }
  mock_resource "aws_iam_role" { defaults = { id = "mock-role", arn = "arn:aws:iam::123456789012:role/mock-role" } }
  mock_resource "aws_iam_instance_profile" { defaults = { arn = "arn:aws:iam::123456789012:instance-profile/mock-runtime" } }
  mock_resource "aws_ssm_document" { defaults = { arn = "arn:aws:ssm:us-east-1:123456789012:document/mock-document" } }
  mock_resource "aws_acm_certificate" {
    defaults = { arn = "arn:aws:acm:us-east-1:123456789012:certificate/mock", domain_validation_options = [{ domain_name = "memoriaslicantropicasgame.gustavodreis.dev.br", resource_record_name = "_validation.memoriaslicantropicasgame.gustavodreis.dev.br", resource_record_type = "CNAME", resource_record_value = "_validation.acm-validations.aws" }] }
  }
  mock_data "aws_caller_identity" { defaults = { account_id = "123456789012" } }
}
variables {
  github_oidc_subject_prefix = "repo:Gusreis7@123/MemoriasLicantropicasGame@456"
}
run "foundation_security" {
  command = plan
  assert {
    condition     = aws_vpc.game.enable_dns_support && aws_vpc.game.enable_dns_hostnames && length(aws_subnet.public) == 2 && length(toset([for subnet in aws_subnet.public : subnet.availability_zone])) == 2
    error_message = "A fundação deve criar sua própria VPC com DNS e duas AZs públicas."
  }
  assert {
    condition     = aws_route.internet.destination_cidr_block == "0.0.0.0/0" && aws_route.internet.gateway_id == aws_internet_gateway.game.id && length(aws_route_table_association.public) == 2 && alltrue([for subnet in aws_subnet.public : subnet.map_public_ip_on_launch])
    error_message = "Ambas as subnets públicas precisam de uma rota para o Internet Gateway."
  }
  assert {
    condition     = aws_subnet.public["primary"].availability_zone == aws_ebs_volume.data.availability_zone
    error_message = "A subnet da instância precisa compartilhar a AZ do volume persistente."
  }
  assert {
    condition     = aws_ebs_volume.data.encrypted && aws_s3_bucket_versioning.all["state"].versioning_configuration[0].status == "Enabled"
    error_message = "Dados e state precisam de proteção persistente."
  }
  assert {
    condition     = length(aws_iam_openid_connect_provider.github) == 0
    error_message = "Não criar outro provedor OIDC quando a conta já possui um."
  }
  assert {
    condition     = jsondecode(aws_iam_role.ci["delivery"].assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == ["repo:Gusreis7@123/MemoriasLicantropicasGame@456:environment:production"]
    error_message = "O delivery deve confiar somente no repo e ambiente previstos."
  }
  assert {
    condition     = !strcontains(aws_iam_role_policy.infrastructure.policy, "iam:PutRolePolicy") && !strcontains(aws_iam_role_policy.infrastructure.policy, "iam:*") && !strcontains(aws_iam_role_policy.delivery.policy, "AWS-RunShellScript")
    error_message = "CI não pode alterar IAM nem enviar shell arbitrário."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.runtime.policy).Statement[0].Condition.StringEquals["bedrock-mantle:Model"] == "qwen.qwen3-32b"
    error_message = "Inferência deve ser restrita ao modelo escolhido."
  }
  assert {
    condition     = jsondecode(aws_ssm_document.admin_tunnel.content).properties.portNumber == "7078" && aws_route53_zone.game.name == "memoriaslicantropicasgame.gustavodreis.dev.br"
    error_message = "Admin privado e DNS precisam permanecer no escopo do jogo."
  }
  assert {
    condition     = alltrue([for policy in [aws_iam_role_policy.infrastructure.policy, aws_iam_role_policy.delivery.policy, aws_iam_role_policy.runtime.policy] : length(policy) <= 10240])
    error_message = "Políticas inline devem respeitar o limite IAM de 10 KiB por papel."
  }

}
