output "foundation" {
  value = {
    aws_region               = var.aws_region
    account_id               = local.account
    project                  = var.project
    domain_name              = var.domain_name
    certificate_arn          = aws_acm_certificate.game.arn
    validation_records       = [for r in aws_route53_record.validation : r.fqdn]
    hosted_zone_id           = aws_route53_zone.game.zone_id
    vpc_id                   = aws_vpc.game.id
    elastic_ip               = aws_eip.game.public_ip
    elastic_ip_allocation_id = aws_eip.game.id
    caddy_image              = var.caddy_image
    public_subnet_ids        = [aws_subnet.public["primary"].id, aws_subnet.public["secondary"].id]
    instance_subnet_id       = aws_subnet.public["primary"].id
    availability_zone        = var.availability_zone
    data_volume_id           = aws_ebs_volume.data.id
    instance_profile         = aws_iam_instance_profile.runtime.name
    releases_bucket          = aws_s3_bucket.releases.id
    api_repository           = aws_ecr_repository.images["api"].repository_url
    web_repository           = aws_ecr_repository.images["web"].repository_url
    redis_image              = var.redis_image
    admin_password_parameter = var.admin_password_parameter
    deploy_document          = aws_ssm_document.deploy.name
  }
}
output "dns_nameservers" { value = aws_route53_zone.game.name_servers }
output "state_bucket" { value = aws_s3_bucket.state.id }
output "infrastructure_role_arn" { value = aws_iam_role.ci["infrastructure"].arn }
output "delivery_role_arn" { value = aws_iam_role.ci["delivery"].arn }
output "admin_tunnel_policy_arn" { value = aws_iam_policy.admin_tunnel.arn }

output "admin_tunnel_document" { value = aws_ssm_document.admin_tunnel.name }
