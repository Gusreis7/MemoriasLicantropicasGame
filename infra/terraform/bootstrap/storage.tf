locals {
  account       = data.aws_caller_identity.current.account_id
  prefix        = "arn:aws"
  parameter_arn = "arn:aws:ssm:${var.aws_region}:${local.account}:parameter${var.admin_password_parameter}"
  state_key     = "production/terraform.tfstate"
  bootstrap_key = "bootstrap/terraform.tfstate"
}
resource "aws_s3_bucket" "state" {
  bucket = "${var.project}-${local.account}-tfstate"
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket" "releases" {
  bucket = "${var.project}-${local.account}-releases"
  lifecycle { prevent_destroy = true }
}
locals { buckets = { state = aws_s3_bucket.state.id, releases = aws_s3_bucket.releases.id } }
resource "aws_s3_bucket_versioning" "all" {
  for_each = local.buckets
  bucket   = each.value
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = local.buckets
  bucket   = each.value
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = local.buckets
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_policy" "tls" {
  for_each = local.buckets
  bucket   = each.value
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Sid       = "TLSOnly", Effect = "Deny", Principal = "*", Action = "s3:*",
    Resource  = ["arn:aws:s3:::${each.value}", "arn:aws:s3:::${each.value}/*"],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}
resource "aws_ecr_repository" "images" {
  for_each             = toset(["api", "web"])
  name                 = "${var.project}-${each.key}"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
  lifecycle { prevent_destroy = true }
}
resource "aws_ebs_volume" "data" {
  availability_zone = var.availability_zone
  size              = var.data_size_gib
  type              = "gp3"
  encrypted         = true
  tags              = { Name = "${var.project}-redis-data" }
  lifecycle { prevent_destroy = true }
}
resource "aws_route53_zone" "game" {
  name    = var.domain_name
  comment = "Delegar estes NS no DNS principal; não gerencia a zona pai."
  lifecycle { prevent_destroy = true }
}
