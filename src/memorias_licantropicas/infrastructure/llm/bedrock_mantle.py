"""Chat Completions no Bedrock Mantle, sem inferências na inicialização."""

from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr, ValidationError

from memorias_licantropicas.contracts.errors import LLMUnavailableError
from memorias_licantropicas.contracts.llm import TokenProvider
from memorias_licantropicas.contracts.model import ChatMessage, LLMResponse


class BedrockMantleClient:
    """Uma requisição de texto por chamada; sem retries ou execução de tools."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | SecretStr | None,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
        token_provider: TokenProvider | None = None,
    ) -> None:
        endpoint = urlsplit(base_url)
        if (
            endpoint.scheme != "https"
            or not endpoint.hostname
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.query
            or endpoint.fragment
        ):
            raise ValueError("O endpoint de inferência deve ser uma URL HTTPS sem credenciais.")
        if not model.strip() or timeout_seconds <= 0 or not 1 <= max_tokens <= 8192:
            raise ValueError("Configuração de inferência inválida.")
        self._api_key = api_key if isinstance(api_key, SecretStr) else SecretStr(api_key or "")
        self._model = model
        self._max_tokens = max_tokens
        self._token_provider = token_provider
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )

    async def complete(self, messages: tuple[ChatMessage, ...]) -> LLMResponse:
        api_key = self._api_key.get_secret_value().strip()
        if not api_key and self._token_provider is not None:
            api_key = (await self._token_provider.get_token()).strip()
        if not api_key:
            raise LLMUnavailableError("Credencial Bedrock não configurada.", code="llm_credentials_missing")
        if not messages:
            raise LLMUnavailableError("A inferência exige contexto de conversa.")
        try:
            response = await self._client.post(
                "chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": self._model,
                    "messages": [message.model_dump() for message in messages],
                    "max_tokens": self._max_tokens,
                    "n": 1,
                    "stream": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return self._parse_response(payload)
        except httpx.TimeoutException:
            raise LLMUnavailableError("O provedor excedeu o prazo de resposta.", code="llm_timeout") from None
        except httpx.HTTPStatusError as exc:
            code = {401: "llm_authentication_failed", 403: "llm_authentication_failed",
                    404: "llm_model_unavailable", 429: "llm_rate_limited"}.get(
                        exc.response.status_code, "llm_unavailable")
            raise LLMUnavailableError("O provedor recusou a requisição de diálogo.", code=code) from None
        except httpx.HTTPError:
            raise LLMUnavailableError("O provedor está inacessível.") from None
        except (ValueError, TypeError, KeyError, ValidationError):
            # Não encaminhar URL, payload, prompt, headers ou mensagem bruta da AWS.
            raise LLMUnavailableError("O serviço de inferência não retornou uma resposta válida.",
                                      code="llm_invalid_response") from None

    def _parse_response(self, payload: object) -> LLMResponse:
        if not isinstance(payload, dict):
            raise ValueError("Formato de resposta inválido.")
        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("Quantidade de respostas inválida.")
        choice = choices[0]
        if isinstance(choice, dict) and choice.get("finish_reason") == "length":
            raise LLMUnavailableError("A resposta do provedor foi truncada.", code="llm_response_truncated")
        if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
            raise ValueError("A resposta não foi concluída.")
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise ValueError("Mensagem de resposta inválida.")
        if message.get("tool_calls") or message.get("function_call"):
            raise ValueError("Ferramentas não são executadas por este adaptador.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Resposta sem texto.")
        model = payload.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Modelo ausente na resposta.")
        usage = payload.get("usage") or {}
        if not isinstance(usage, dict):
            raise ValueError("Metadados de uso inválidos.")
        token_counts = [usage.get("prompt_tokens"), usage.get("completion_tokens")]
        if any(value is not None and (type(value) is not int or value < 0) for value in token_counts):
            raise ValueError("Contagem de tokens inválida.")
        return LLMResponse(
            content=content.strip(),
            model=model,
            input_tokens=token_counts[0],
            output_tokens=token_counts[1],
        )

    async def aclose(self) -> None:
        await self._client.aclose()
