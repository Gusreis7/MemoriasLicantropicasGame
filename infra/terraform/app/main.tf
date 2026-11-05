resource "aws_security_group" "alb" {
  name_prefix = "mlgame-alb-"
  description = "Public HTTPS and HTTP redirect only"
  vpc_id      = local.foundation.vpc_id
}
resource "aws_security_group" "host" {
  name_prefix = "mlgame-host-"
  description = "ALB to web only; no public SSH/admin/API/Redis"
  vpc_id      = local.foundation.vpc_id
}
resource "aws_vpc_security_group_ingress_rule" "public" {
  for_each          = toset(["80", "443"])
  security_group_id = aws_security_group.alb.id
  ip_protocol       = "tcp"
  from_port         = tonumber(each.key)
  to_port           = tonumber(each.key)
  cidr_ipv4         = "0.0.0.0/0"
}
resource "aws_vpc_security_group_egress_rule" "alb_target" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.host.id
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
}
resource "aws_vpc_security_group_ingress_rule" "host" {
  security_group_id            = aws_security_group.host.id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
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
  subnet_id                   = one([for subnet in data.aws_subnet.public : subnet.id if subnet.availability_zone == local.foundation.availability_zone])
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.host.id]
  iam_instance_profile        = local.foundation.instance_profile
  user_data_replace_on_change = true
  user_data_base64 = base64gzip(templatefile("${path.module}/cloud-init.yaml.tftpl", {
    files = {
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
      condition     = alltrue([for subnet in data.aws_subnet.public : subnet.vpc_id == local.foundation.vpc_id && subnet.map_public_ip_on_launch]) && length(toset([for subnet in data.aws_subnet.public : subnet.availability_zone])) >= 2
      error_message = "Forneça subnets públicas da VPC indicada, em pelo menos duas AZs."
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
resource "aws_lb" "game" {
  name                       = "mlgame-production"
  load_balancer_type         = "application"
  internal                   = false
  security_groups            = [aws_security_group.alb.id]
  subnets                    = local.foundation.public_subnet_ids
  drop_invalid_header_fields = true
  enable_deletion_protection = false
  desync_mitigation_mode     = "strictest"
  idle_timeout               = 150
}
resource "aws_lb_target_group" "game" {
  name     = "mlgame-production"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = local.foundation.vpc_id
  health_check {
    path    = "/health"
    matcher = "200"
  }
}
resource "aws_lb_target_group_attachment" "game" {
  target_group_arn = aws_lb_target_group.game.arn
  target_id        = aws_instance.game.id
  port             = 8080
}
resource "aws_acm_certificate_validation" "game" {
  certificate_arn         = local.foundation.certificate_arn
  validation_record_fqdns = local.foundation.validation_records
  timeouts { create = "20m" }
}
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.game.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.game.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.game.arn
  }
}
resource "aws_lb_listener" "redirect" {
  load_balancer_arn = aws_lb.game.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}
resource "aws_route53_record" "game" {
  zone_id = local.foundation.hosted_zone_id
  name    = local.foundation.domain_name
  type    = "A"
  alias {
    name                   = aws_lb.game.dns_name
    zone_id                = aws_lb.game.zone_id
    evaluate_target_health = true
  }
}
output "instance_id" { value = aws_instance.game.id }
output "game_url" { value = "https://${local.foundation.domain_name}" }
output "target_group_arn" { value = aws_lb_target_group.game.arn }
