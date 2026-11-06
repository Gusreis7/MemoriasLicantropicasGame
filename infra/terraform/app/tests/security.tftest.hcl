mock_provider "aws" {
  mock_data "aws_ssm_parameter" { defaults = { value = "ami-0123456789abcdef0" } }
}
variables { state_bucket = "mock-state-only" }
override_data {
  target = data.terraform_remote_state.bootstrap
  values = { outputs = { foundation = {
    aws_region               = "us-east-1", account_id = "123456789012", project = "memorias-licantropicas",
    domain_name              = "memoriaslicantropicasgame.gustavodreis.dev.br", hosted_zone_id = "Z12345678",
    certificate_arn          = "arn:aws:acm:us-east-1:123456789012:certificate/01234567-0123-0123-0123-012345678901",
    validation_records       = ["_test.memoriaslicantropicasgame.gustavodreis.dev.br"],
    vpc_id                   = "vpc-0123456789abcdef0", public_subnet_ids = ["subnet-0123456789abcdef0", "subnet-0123456789abcdef1"],
    availability_zone        = "us-east-1a", instance_subnet_id = "subnet-0123456789abcdef0", data_volume_id = "vol-0123456789abcdef0", instance_profile = "mock-runtime",
    releases_bucket          = "mock-releases", api_repository = "123456789012.dkr.ecr.us-east-1.amazonaws.com/game-api",
    web_repository           = "123456789012.dkr.ecr.us-east-1.amazonaws.com/game-web", redis_image = "redis@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    admin_password_parameter = "/game/admin-password", deploy_document = "game-deploy"
  } } }
}
override_data {
  target = data.aws_subnet.public["subnet-0123456789abcdef0"]
  values = { id = "subnet-0123456789abcdef0", vpc_id = "vpc-0123456789abcdef0", availability_zone = "us-east-1a", map_public_ip_on_launch = true }
}
override_data {
  target = data.aws_subnet.public["subnet-0123456789abcdef1"]
  values = { id = "subnet-0123456789abcdef1", vpc_id = "vpc-0123456789abcdef0", availability_zone = "us-east-1b", map_public_ip_on_launch = true }
}
run "workload_security" {
  command = plan
  assert {
    condition     = aws_instance.game.instance_type == "m7i-flex.large" && aws_instance.game.metadata_options[0].http_tokens == "required" && aws_instance.game.root_block_device[0].encrypted
    error_message = "Instância, IMDSv2 e disco precisam cumprir o contrato."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.host.from_port == 8080 && length(aws_vpc_security_group_ingress_rule.public) == 2
    error_message = "Só o listener do jogo pode ser exposto ao ALB; nenhum admin, SSH, Redis ou API."
  }
  assert {
    condition     = aws_lb_listener.https.port == 443 && aws_lb_listener.redirect.default_action[0].redirect[0].protocol == "HTTPS"
    error_message = "O tráfego público deve usar TLS."
  }
}
