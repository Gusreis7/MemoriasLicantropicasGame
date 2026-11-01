"""Tokens por requisição a partir do perfil local; sem login/chamada no startup."""

import asyncio
from datetime import timedelta

from aws_bedrock_token_generator import provide_token
from botocore.credentials import CredentialProvider
from botocore.exceptions import BotoCoreError, ClientError
from botocore.session import Session

from memorias_licantropicas.contracts.errors import LLMUnavailableError


class _ProfileCredentials(CredentialProvider):
    def __init__(self, profile: str):
        self._profile = profile

    def load(self):
        return Session(profile=self._profile).get_credentials()


class ProfileTokenProvider:
    def __init__(self, profile: str, region: str):
        self._profile = profile
        self._region = region

    def _generate(self) -> str:
        try:
            return provide_token(region=self._region,
                                 aws_credentials_provider=_ProfileCredentials(self._profile),
                                 expiry=timedelta(minutes=15))
        except (BotoCoreError, ClientError, RuntimeError, ValueError):
            raise LLMUnavailableError("Não foi possível obter credenciais do perfil AWS.") from None

    async def get_token(self) -> str:
        return await asyncio.to_thread(self._generate)
