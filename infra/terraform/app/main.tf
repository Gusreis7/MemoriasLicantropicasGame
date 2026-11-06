resource "aws_security_group" "host" {
  name_prefix = "mlgame-host-"
  description = "Public HTTP/HTTPS only; admin via SSM, API and Redis private"
  vpc_id      = local.foundation.vpc_id
}
resource "aws_vpc_security_group_ingress_rule" "public" {
  for_each          = toset(["80", "443"])
  security_group_id = aws_security_group.host.id
  ip_protocol       = "tcp"
  from_port         = tonumber(each.key)
  to_port           = tonumber(each.key)
  cidr_ipv4         = "0.0.0.0/0"
}
resource "aws_vpc_security_group_egress_rule" "host" {
  for_each          = toset(["80", "443"])
  security_group_id = aws_security_group.host.id
  ip_protocol       = "tcp"
  from_port         = tonumber(each.key)
  to_port           = tonumber(each.key)
  cidr_ipv4         = "0.0.0.0/0"
}
resource "aws_instance" "game" {
  ami                         = data.aws_ssm_parameter.ami.value
  instance_type               = "m7i-flex.large"
  subnet_id                   = local.foundation.instance_subnet_id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.host.id]
  iam_instance_profile        = local.foundation.instance_profile
  user_data_replace_on_change = true
  user_data_base64 = base64gzip(templatefile("${path.module}/cloud-init.yaml.tftpl", {
    files = {
      "/etc/ml-game/Caddyfile"              = file("${path.module}/../../../deploy/production/Caddyfile")
      "/etc/ml-game/compose.yaml"           = file("${path.module}/../../../deploy/production/compose.yaml")
      "/etc/ml-game/game.conf"              = file("${path.module}/../../../deploy/production/game.conf")
      "/etc/ml-game/proxy-game.conf"        = file("${path.module}/../../../deploy/production/proxy-game.conf")
      "/etc/ml-game/admin.conf"             = file("${path.module}/../../../deploy/admin.conf")
      "/etc/ml-game/config.json"            = jsonencode(local.foundation)
      "/etc/systemd/system/ml-game.service" = file("${path.module}/../../../deploy/production/ml-game.service")
    }
    deploy_script    = file("${path.module}/../../../deploy/production/ml-deploy.py")
    firewall_script  = file("${path.module}/../../../deploy/production/container-firewall.sh")
    bootstrap_script = file("${path.module}/../../../deploy/production/bootstrap-host.sh")
  }))
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "disabled"
  }
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 16
    encrypted             = true
    delete_on_termination = true
  }
  volume_tags = { Project = local.foundation.project, ManagedBy = "Terraform", Environment = "production" }
  tags        = { Name = "${local.foundation.project}-production" }
  lifecycle {
    precondition {
      condition     = alltrue([for subnet in data.aws_subnet.public : subnet.vpc_id == local.foundation.vpc_id && subnet.map_public_ip_on_launch]) && length(toset([for subnet in data.aws_subnet.public : subnet.availability_zone])) >= 2 && one([for subnet in data.aws_subnet.public : subnet.availability_zone if subnet.id == local.foundation.instance_subnet_id]) == local.foundation.availability_zone
      error_message = "A rede do bootstrap precisa de duas AZs públicas e a EC2 deve usar a AZ do volume persistente."
    }
  }
}
resource "aws_volume_attachment" "data" {
  device_name                    = "/dev/sdf"
  volume_id                      = local.foundation.data_volume_id
  instance_id                    = aws_instance.game.id
  stop_instance_before_detaching = true
  force_detach                   = false
}

resource "aws_eip_association" "game" {
  allocation_id       = local.foundation.elastic_ip_allocation_id
  instance_id         = aws_instance.game.id
  allow_reassociation = false
}
output "instance_id" { value = aws_instance.game.id }
output "public_ip" { value = local.foundation.elastic_ip }
output "elastic_ip_allocation_id" { value = local.foundation.elastic_ip_allocation_id }
output "game_url" { value = "https://${local.foundation.domain_name}" }
