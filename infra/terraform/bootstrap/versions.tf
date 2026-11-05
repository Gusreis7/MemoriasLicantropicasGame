terraform {
  required_version = ">= 1.11.4, < 2.0"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.0" } }
}
provider "aws" {
  region = var.aws_region
  default_tags { tags = { Project = var.project, ManagedBy = "Terraform", Environment = "production" } }
}
data "aws_caller_identity" "current" {}
