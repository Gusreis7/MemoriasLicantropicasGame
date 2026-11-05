mock_provider "aws" {
  mock_resource "aws_acm_certificate" {
    defaults = { domain_validation_options = [{ domain_name = "memoriaslicantropicasgame.gustavodreis.dev.br", resource_record_name = "_validation.memoriaslicantropicasgame.gustavodreis.dev.br", resource_record_type = "CNAME", resource_record_value = "_validation.acm-validations.aws" }] }
  }
  mock_data "aws_caller_identity" { defaults = { account_id = "123456789012" } }
}
variables {
  vpc_id                     = "vpc-0123456789abcdef0"
  public_subnet_ids          = ["subnet-0123456789abcdef0", "subnet-0123456789abcdef1"]
  github_oidc_subject_prefix = "repo:Gusreis7@123/MemoriasLicantropicasGame@456"
}
run "foundation_security" {
  command = apply
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
