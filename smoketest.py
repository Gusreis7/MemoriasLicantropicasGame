"""Uma inferência real no Mantle usando o login AWS local, sem Redis.

Execute: uv run python smoketest.py --profile terraform --region us-east-1
"""

import argparse
import asyncio
import os
import sys
from datetime import timedelta

from aws_bedrock_token_generator import provide_token
from botocore.exceptions import BotoCoreError, ClientError

from memorias_licantropicas.contracts.errors import LLMUnavailableError
from memorias_licantropicas.contracts.model import ChatMessage
from memorias_licantropicas.infrastructure.llm.bedrock_mantle import BedrockMantleClient
from memorias_licantropicas.settings import Settings


async def run(settings: Settings) -> None:
    # Usa AWS_PROFILE e o cache do login local. Não persiste nem imprime o token.
    token = provide_token(region=settings.aws_region, expiry=timedelta(minutes=15))
    client = BedrockMantleClient(
        base_url=settings.mantle_base_url,
        api_key=token,
        model=settings.bedrock_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
    )
    try:
        messages = (
            ChatMessage(
                role="user",
                content=(
                    "Você conhece Machado de Assis? Responda brevemente em português, "
                    "citando duas obras e algumas características de sua escrita."
                ),
            ),
        )
        print("Enviado (user):", messages[0].content, flush=True)
        response = await client.complete(messages)
        print("Modelo:", response.model)
        print("Recebido (assistant):", response.content)
        print("Tokens de entrada:", response.input_tokens)
        print("Tokens de saída:", response.output_tokens)
    finally:
        await client.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Testa uma chamada real ao Mantle com token temporário do perfil AWS local.",
    )
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE", "terraform"))
    parser.add_argument("--region", help="Região AWS; padrão de AWS_REGION/.env ou us-east-1.")
    args = parser.parse_args()
    os.environ["AWS_PROFILE"] = args.profile
    try:
        settings = Settings()
        if args.region:
            settings = settings.model_copy(update={"aws_region": args.region})
        asyncio.run(run(settings))
    except (BotoCoreError, ClientError) as error:
        print(
            f"Falha ao obter credenciais AWS ({type(error).__name__}). "
            f"Confira a sessão com: aws sts get-caller-identity --profile {args.profile}",
            file=sys.stderr,
        )
        return 1
    except LLMUnavailableError as error:
        print(f"Falha na inferência: {error} Confira região, modelo e permissões Mantle.", file=sys.stderr)
        return 1
    except ValueError:
        print("Configuração inválida. Confira .env e os argumentos fornecidos.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
