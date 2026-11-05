resource "aws_acm_certificate" "game" {
  domain_name       = var.domain_name
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}
resource "aws_route53_record" "validation" {
  for_each = toset([var.domain_name])
  zone_id  = aws_route53_zone.game.zone_id
  name     = one([for option in aws_acm_certificate.game.domain_validation_options : option.resource_record_name if option.domain_name == each.key])
  type     = "CNAME"
  records  = [one([for option in aws_acm_certificate.game.domain_validation_options : option.resource_record_value if option.domain_name == each.key])]
  ttl      = 60
}
