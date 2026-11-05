"""Tokens por requisição a partir do perfil local; sem login/chamada no startup."""

import asyncio
from datetime import timedelta
import os
from pathlib import Path
import shutil
import threading

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
    _refresh_lock = threading.Lock()

    def __init__(self, profile: str | None, region: str, *,
                 refresh_source_dir: str | Path | None = None,
                 config_dir: str | Path | None = None):
        self._profile = profile
        self._region = region
        self._refresh_source_dir = (Path(refresh_source_dir)
                                    if refresh_source_dir else None)
        self._config_dir = Path(config_dir) if config_dir else Path.home() / ".aws"

    def _provide_token(self) -> str:
        return provide_token(
            region=self._region,
            aws_credentials_provider=_ProfileCredentials(self._profile) if self._profile else None,
            expiry=timedelta(minutes=15),
        )

    def _refresh_profile_cache(self) -> bool:
        source = self._refresh_source_dir
        if source is None or not source.is_dir():
            return False
        has_source_files = False
        with self._refresh_lock:
            for source_file in source.rglob("*"):
                if source_file.is_symlink() or not source_file.is_file():
                    continue
                has_source_files = True
                destination = self._config_dir / source_file.relative_to(source)
                try:
                    if (destination.is_file()
                            and destination.stat().st_mtime_ns >= source_file.stat().st_mtime_ns):
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    temporary = destination.with_name(
                        f".{destination.name}.{os.getpid()}.{threading.get_ident()}.tmp"
                    )
                    try:
                        shutil.copy2(source_file, temporary)
                        temporary.chmod(0o600)
                        os.replace(temporary, destination)
                    finally:
                        temporary.unlink(missing_ok=True)
                except OSError:
                    continue
        # Outro provider pode ter copiado os mesmos arquivos enquanto esta
        # chamada aguardava o lock. Ainda assim vale repetir a geração uma vez.
        return has_source_files

    def _generate(self) -> str:
        failures = (BotoCoreError, ClientError, RuntimeError, ValueError, OSError)
        try:
            return self._provide_token()
        except failures:
            if self._refresh_profile_cache():
                try:
                    return self._provide_token()
                except failures:
                    pass
            raise LLMUnavailableError("Não foi possível obter credenciais do perfil AWS.",
                                      code="llm_credentials_unavailable") from None

    async def get_token(self) -> str:
        return await asyncio.to_thread(self._generate)
