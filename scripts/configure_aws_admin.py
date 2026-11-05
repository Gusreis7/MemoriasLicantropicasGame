"""Ação manual: gravar senha administrativa no SSM sem args, logs ou Terraform state."""

import argparse, getpass
from botocore.session import Session


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", default="terraform")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()
    password = getpass.getpass("Senha do admin (mínimo 24 caracteres): ")
    confirmation = getpass.getpass("Confirme a senha: ")
    if password != confirmation or not 24 <= len(password) <= 1024:
        raise SystemExit("Senhas diferentes ou muito curtas.")
    client = Session(profile=args.profile).create_client("ssm", region_name=args.region)
    client.put_parameter(
        Name="/memorias-licantropicas/production/admin-password",
        Type="SecureString",
        Value=password,
        Overwrite=args.overwrite,
    )
    print("Parâmetro administrativo gravado; valor não exibido.")


if __name__ == "__main__":
    main()
