"""Prepara .env sem sobrescrever configuração existente nem imprimir segredos."""

import argparse
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset-admin-password", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = root / ".env"
    lines = (path.read_text() if path.exists() else (root / ".env.example").read_text()).splitlines()
    values = {line.split("=", 1)[0]: line.split("=", 1)[1]
              for line in lines if "=" in line and not line.lstrip().startswith("#")}
    if args.reset_admin_password or not values.get("ADMIN_PASSWORD", "").strip().strip("\"'"):
        lines = [line for line in lines if not line.startswith("ADMIN_PASSWORD=")]
        lines.append("ADMIN_PASSWORD=" + secrets.token_urlsafe(24))
    if "ADMIN_USERNAME" not in values:
        lines.append("ADMIN_USERNAME=admin")
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)
    print("Configuração local pronta. Usuário e senha estão em ADMIN_USERNAME/ADMIN_PASSWORD no .env.")
    print("O arquivo não é versionado. Reinicie a API depois de alterar as credenciais.")


if __name__ == "__main__":
    main()
