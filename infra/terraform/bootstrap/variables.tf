variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "project" {
  type    = string
  default = "memorias-licantropicas"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,24}$", var.project))
    error_message = "Use um prefixo curto e estável em minúsculas."
  }
}
variable "domain_name" {
  type    = string
  default = "memoriaslicantropicasgame.gustavodreis.dev.br"
  validation {
    condition     = var.domain_name == "memoriaslicantropicasgame.gustavodreis.dev.br"
    error_message = "Esta base está restrita ao domínio do jogo."
  }
}
variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && can(cidrsubnet(var.vpc_cidr, 8, 1)) && can(regex("/16$", var.vpc_cidr))
    error_message = "Informe uma rede IPv4 /16 para dividir em subnets públicas /24."
  }
}
variable "availability_zone" {
  type    = string
  default = "us-east-1a"
}
variable "secondary_availability_zone" {
  type    = string
  default = "us-east-1b"
  validation {
    condition     = var.secondary_availability_zone != var.availability_zone
    error_message = "As duas subnets públicas precisam de AZs distintas."
  }
}
variable "github_oidc_subject_prefix" {
  type        = string
  description = "Prefixo sub efetivo do repositório; confira IDs imutáveis ou formato legado no GitHub."
  validation {
    condition     = can(regex("^repo:Gusreis7(@[0-9]+)?/MemoriasLicantropicasGame(@[0-9]+)?$", var.github_oidc_subject_prefix))
    error_message = "Informe o sub exato do repo, sem wildcard; IDs devem ser reais, não placeholders."
  }
}
variable "create_github_oidc_provider" {
  type        = bool
  default     = false
  description = "Na conta consultada o provider do GitHub já existe; reutilizar é o padrão."
}
variable "admin_password_parameter" {
  type    = string
  default = "/memorias-licantropicas/production/admin-password"
}
variable "data_size_gib" {
  type    = number
  default = 20
}
variable "redis_image" {
  type    = string
  default = "redis@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499"
  validation {
    condition     = can(regex("^redis@sha256:[a-f0-9]{64}$", var.redis_image))
    error_message = "Fixe a imagem oficial Redis por digest."
  }
}
variable "caddy_image" {
  type    = string
  default = "caddy@sha256:fc9cbc100585871d18d4e451cca7021785c90a7006087427ae5ceb3e4efe6424"
  validation {
    condition     = can(regex("^caddy@sha256:[a-f0-9]{64}$", var.caddy_image))
    error_message = "Fixe a imagem oficial Caddy linux/amd64 por digest."
  }
}
