# Rede permanente do projeto: remover a aplicação não remove a rede ou o EBS.
resource "aws_vpc" "game" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.project}-vpc" }
  lifecycle { prevent_destroy = true }
}
resource "aws_internet_gateway" "game" {
  vpc_id = aws_vpc.game.id
  tags   = { Name = "${var.project}-internet" }
}
locals {
  public_zones = { primary = var.availability_zone, secondary = var.secondary_availability_zone }
}
resource "aws_subnet" "public" {
  for_each                = local.public_zones
  vpc_id                  = aws_vpc.game.id
  availability_zone       = each.value
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, each.key == "primary" ? 0 : 1)
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project}-public-${each.key}" }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.game.id
  tags   = { Name = "${var.project}-public" }
}
resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.game.id
}
resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}
