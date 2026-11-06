# Endereço persistente: destruir/recriar app não libera o IP registrado no DNS.
resource "aws_eip" "game" {
  domain = "vpc"
  tags   = { Name = "${var.project}-public" }
  lifecycle { prevent_destroy = true }
}
output "public_ip" { value = aws_eip.game.public_ip }
output "elastic_ip_allocation_id" { value = aws_eip.game.id }
