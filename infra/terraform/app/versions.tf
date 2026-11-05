terraform {
  required_version = ">= 1.11.4, < 2.0"
  backend "s3" {}
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.0" } }
}
provider "aws" {
  region = var.aws_region
  default_tags { tags = { Project = local.foundation.project, ManagedBy = "Terraform", Environment = "production" } }
}
variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "state_bucket" {
  type = string
}
variable "bootstrap_key" {
  type    = string
  default = "bootstrap/terraform.tfstate"
}
data "terraform_remote_state" "bootstrap" {
  backend = "s3"
  config  = { bucket = var.state_bucket, key = var.bootstrap_key, region = var.aws_region }
}
locals { foundation = data.terraform_remote_state.bootstrap.outputs.foundation }
data "aws_vpc" "existing" { id = local.foundation.vpc_id }
data "aws_subnet" "public" {
  for_each = toset(local.foundation.public_subnet_ids)
  id       = each.value
}
data "aws_ssm_parameter" "ami" { name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64" }
