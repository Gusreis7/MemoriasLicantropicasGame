"""Senha por scrypt e sessões opacas Redis; nenhum token chega ao JavaScript."""

import asyncio
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime

from fastapi import HTTPException
from redis.exceptions import RedisError

from memorias_licantropicas.contracts.errors import StorageUnavailableError

COOKIE_NAME = "ml_admin_session"
COOKIE_PATH = "/admin/api"
_FAILURE_LIMIT = 10
_FAILURE_WINDOW = 300


def _error(code: int, detail: str) -> HTTPException:
    return HTTPException(code, detail, headers={"Cache-Control": "no-store"})


def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)


class AdminAuth:
    def __init__(self, client, prefix, settings):
        self._client = client
        self._prefix = prefix
        self.username = settings.admin_username
        self.session_seconds = settings.admin_session_seconds
        self.cookie_secure = settings.admin_cookie_secure
        self._origins = {origin.strip().rstrip("/") for origin in settings.admin_allowed_origins.split(",") if origin.strip()}
        password = settings.admin_password.get_secret_value() if settings.admin_password else ""
        self._configured = bool(password and self.username)
        self._salt = secrets.token_bytes(16)
        self._password_hash = _derive(password or secrets.token_urlsafe(32), self._salt)

    def check_origin(self, origin: str | None) -> None:
        # CLI sem Origin é permitido; browsers cross-origin recebem rejeição explícita.
        if origin is not None and origin.rstrip("/") not in self._origins:
            raise _error(403, "Origem não permitida.")

    def _session_key(self, token: str) -> str:
        digest = hashlib.sha256(token.encode()).hexdigest()
        return f"{self._prefix}:admin:session:{digest}"

    def _attempts_key(self, remote_ip: str) -> str:
        digest = hashlib.sha256(remote_ip.encode()).hexdigest()
        return f"{self._prefix}:admin:attempts:{digest}"

    async def login(self, username: str, password: str, remote_ip: str) -> str:
        if not self._configured:
            raise _error(503, "Acesso administrativo não configurado.")
        if not 1 <= len(username) <= 128 or not 1 <= len(password) <= 1024:
            raise _error(401, "Usuário ou senha inválidos.")
        key = self._attempts_key(remote_ip)
        try:
            failures = int(await self._client.get(key) or 0)
            if failures >= _FAILURE_LIMIT:
                raise HTTPException(429, "Muitas tentativas. Aguarde antes de tentar novamente.",
                                    headers={"Retry-After": str(_FAILURE_WINDOW), "Cache-Control": "no-store"})
            supplied = await asyncio.to_thread(_derive, password, self._salt)
            valid_password = hmac.compare_digest(self._password_hash, supplied)
            valid_username = hmac.compare_digest(self.username.encode(), username.encode())
            if not (valid_username and valid_password):
                async with self._client.pipeline(transaction=True) as pipe:
                    pipe.incr(key)
                    pipe.expire(key, _FAILURE_WINDOW, nx=True)
                    await pipe.execute()
                raise _error(401, "Usuário ou senha inválidos.")
            token = secrets.token_urlsafe(32)
            record = json.dumps({"username": self.username, "created_at": datetime.now(UTC).isoformat()})
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.set(self._session_key(token), record, ex=self.session_seconds)
                pipe.delete(key)
                await pipe.execute()
            return token
        except (RedisError, ValueError, TypeError):
            raise StorageUnavailableError("Autenticação temporariamente indisponível.") from None

    async def session(self, token: str | None) -> str:
        if not token or len(token) > 256:
            raise _error(401, "Autenticação necessária.")
        if not self._configured:
            raise _error(503, "Acesso administrativo não configurado.")
        try:
            raw = await self._client.get(self._session_key(token))
            if raw is None:
                raise _error(401, "Sessão expirada ou inválida.")
            record = json.loads(raw)
            if not isinstance(record, dict) or record.get("username") != self.username:
                raise _error(401, "Sessão expirada ou inválida.")
            return self.username
        except (RedisError, ValueError, TypeError):
            raise StorageUnavailableError("Autenticação temporariamente indisponível.") from None

    async def logout(self, token: str | None) -> None:
        if token and len(token) <= 256:
            try:
                await self._client.delete(self._session_key(token))
            except RedisError:
                raise StorageUnavailableError("Autenticação temporariamente indisponível.") from None
